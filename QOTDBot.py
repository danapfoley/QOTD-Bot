#from flask import Flask, request, make_response, Response
import os
import time
import re
import json
from slackclient import SlackClient

from QuestionKeeper import *
from ScoreKeeper import *

# instantiate Slack client
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
SLACK_TOKEN = os.environ.get('SLACK_TOKEN')

slack_client = SlackClient(SLACK_BOT_TOKEN)
# starterbot's user ID in Slack: value is assigned after the bot starts up
bot_id = "UNKNOWN"

###app = Flask(__name__)

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
HELP_COMMAND = "help"
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"
QOTD_CHANNEL = "G9DHWHZP1"


# trackers
questionKeeper = QuestionKeeper()
scoreKeeper = ScoreKeeper()

#Commands stuff
#----------------------------------

def say(channel, response):
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response,
        icon_emoji=':robot_face:'
    )

def getNameByID(userID):
    attemptedNameJson = slack_client.api_call(
        "users.info",
        token = SLACK_BOT_TOKEN,
        user = userID
    )
 
    if attemptedNameJson["ok"]:
        if attemptedNameJson["user"]["profile"]["display_name"] != "":
            userName = attemptedNameJson["user"]["profile"]["display_name"]
        else:
            userName = attemptedNameJson["user"]["profile"]["real_name"]
    else:
        userName = userID

    return userName

def getDirectChannel(userID):
    dmChannel = slack_client.api_call(
        "conversations.open",
        users = userID
    )

    return dmChannel["channel"]["id"]


def checkPublic(messageEvent):
    if not is_event_private(messageEvent):
        return "You can't use this command in a public channel. Message me directly instead"
    else:
        return ""

def help(messageEvent):
    channel, args = messageEvent["channel"], messageEvent["text"]
    response = ""
    if args:
        response += "Not sure what you meant by \"" + args + "\", but here's some help if you need it!\n"
    response += "(Some helpful stuff)"
    say(channel, response)

def scores(messageEvent):
    channel, args = messageEvent["channel"], messageEvent["text"]
    response = scoreKeeper.getTodayScores()
    response += scoreKeeper.getTotalScores()
    say(channel, response)
    return response

def question(messageEvent):
    channel = messageEvent["channel"]
    args = messageEvent["text"].split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    response = ""
    
    if identifier == "help":
        response += "Usage:\n"
    if identifier in ["help", "usage"]:
        response += "`question [identifier] [question] : <answer>`\n"\
                 +  "`question [identifier] remove`\n"
        say(channel, response)
        return response
    if identifier == "remove":
        response += "You probably meant to use `question [identifier] remove`\n"
        say(channel, response)
        return response
    if len(args) < 2:
        say(channel, "This command needs more arguments! Type \"question help\" for usage")
        return
    
    args = args[1] #no longer holding identifier
    colonIndex = args.rfind(":")
    if colonIndex == -1:
        question = args.strip()
        answer = ""
    else:
        question = args[:colonIndex].strip()
        answer = args[colonIndex+1:].strip()

    if question == "remove":
        if questionKeeper.removeQuestion(identifier):
            response = "Okay, I removed that question"
            say(channel, response)
            return response
        else:
            response = "I didn't find a question with that ID"
            say(channel, response) 
            return response

    #only get here if a valid question input format is given
    questionAdded = questionKeeper.addQuestion(userID = messageEvent["user"], qID = identifier, questionText = question, correctAnswer = answer)
    
    if questionAdded:
        response = "Okay, I added your question with ID " + identifier + ".\n"\
                 + "Use `publish` to make your questions publicly available, "\
                 + "or `remove` to remove it"
    else:
        response = "A question with this ID already exists right now. Please use a different one"

    say(channel, response)
    return response

def questions(messageEvent):
    output = questionKeeper.listQuestions()
    
    if output == "":
        output = "There are no currently active questions"
    else:
        output = "Here are all the currently active questions:\n" + output
    
    say(messageEvent["channel"], output)
    return output

def publish(messageEvent):
    channel = messageEvent["channel"]

    args = messageEvent["text"].split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    if identifier == "help":
        response += "Usage: "
    if identifier in ["help", "usage"]:
        response += "`publish <identifier>`\n"
        say(channel, response)
        return response
    if identifier != "":
        publishResponse = questionKeeper.publishByID(identifier)
        if publishResponse == "published":
            response = "Okay, I published question " + identifier + ".\n"
        elif publishResponse == "already published":
            response = identifier + " is already published.\n"
        else:
            response = "I couldn't find a question with that ID.\n"
    else:
        questionKeeper.publishAllByUser(messageEvent["user"])
        response = "Okay, I've published all of your questions\n"

    newQuestions = questionKeeper.firstTimeDisplay()
    if newQuestions != "":
        say(QOTD_CHANNEL, "New questions: " + newQuestions)

    say(channel, response)
    return response
    


def answer(messageEvent):
    channel, userID = messageEvent["channel"], messageEvent["user"]

    args = messageEvent["text"].split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    response = checkPublic(messageEvent)

    if response != "":
        say(channel, response)
        return response
    
    if identifier == "help":
        response += "Usage: "
    if identifier in ["help", "usage"]:
        response += "`answer [identifier] [your answer]`\n"
        say(channel, response)
        return response
    if len(args) < 2:
        say(channel, "This command needs more arguments! Type \"answer help\" for usage")
        return
    
    inputAnswer = args[1] #no longer holding identifier
    checkResponse = questionKeeper.checkAnswer(messageEvent["user"], identifier, inputAnswer)

    if checkResponse == "correct":
        response = "Correct! I'll give you a point\n"
        addPoint(messageEvent)
    elif checkResponse == "incorrect":
        response = "I think that's incorrect. Though I'm not very good at validating answers yet.\n"
    elif checkResponse == "already answered":
        response = "You already answered that question!"
    elif checkResponse == "needsManual":
        userWhoSubmitted = questionKeeper.getSubmitterByQID(identifier)
        response = "This question needs to be validated manually. I'll ask " + userWhoSubmitted + " to check your answer."
        directUserChannel = getDirectChannel(userWhoSubmitted)
        say(directUserChannel, getNameByID(userID) + " has answered \"" + inputAnswer + "\" for your question,\n" + questionKeeper.getQuestionByID(identifier).prettyPrint() \
            + "\nIs this correct?\n(I don't know how to respond to this yet)")
    else:
        response = "I couldn't find a question with that ID.\n Use `questions` to find the proper ID.\n"

    say(channel, response)
    return response


def hello(messageEvent):
    channel, userID = messageEvent["channel"], messageEvent["user"]

    userName = getNameByID(userID)

    response = "Hello " + userName + ", I'm QOTD Bot!"
    response += "\nUser ID: " + userID + "\nChannel ID: " + channel
    say(channel, response)

def addPoint(messageEvent):
    userID = messageEvent["user"]
    if not scoreKeeper.userExists(userID):
        scoreKeeper.addNewUser(userID)
        scoreKeeper.addNameToUser(userID, getNameByID(userID))
    scoreKeeper.addUserPoint(userID)

    say(QOTD_CHANNEL, "Point for " + getNameByID(userID) + "!")

def addPoints(messageEvent):
    userID = messageEvent["user"]

    channel = messageEvent["channel"]

    args = messageEvent["text"].split(' ', 1)
    numPoints = args[0] if len(args) > 0 else ""

    if numPoints == "help":
        response += "Usage: "
    if numPoints in ["help", "usage"]:
        response += "`add-points [# points]`\n"
        say(channel, response)
        return response
    if len(args) < 1:
        say(channel, "This command needs more arguments! Type \"add-points help\" for usage")
        return

    if not scoreKeeper.userExists(userID):
        scoreKeeper.addNewUser(userID)
        scoreKeeper.addNameToUser(userID, getNameByID(userID))
    scoreKeeper.addUserPoints(userID, int(numPoints))

def channelID(messageEvent):
    say(messageEvent["channel"],"The channel we're in now is: " + messageEvent["channel"])

commandsDict = {
    "help" : help,
    "scores" : scores,
    "score" : scores,
    "points" : scores,
    "question" : question,
    "q" : question,
    "questions" : questions,
    "qs" : questions,
    "publish" : publish,
    "answer" : answer,
    "a" : answer,
    "hello" : hello,
    "add-point" : addPoint,
    "add-points" : addPoints,
    "channel-id" : channelID
}


#----------------------------------

def is_channel_private(channel):
    return channel.startswith('D')

def is_event_private(messageEvent):
    """Checks if private slack channel"""
    return messageEvent['channel'].startswith('D')


def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            processedEvent = parse_direct_mention(event)
            if processedEvent:
                print(getNameByID(event["user"]) + "says: " + event["text"])
                return processedEvent
    return None

def parse_direct_mention(event):
    message_text = event["text"]
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    #If direct mention...
    if matches and matches.group(1) == bot_id:
        event["text"] = matches.group(2).strip()
        #return (matches.group(1), matches.group(2).strip())
        return event
    #If private message (no mention necessary)
    elif is_event_private(event):
        #return (bot_id, message_text)
        return event
    else:
        return None

def handle_command(event):
    """
        Executes bot command if the command is known
    """
    # This is where you start to implement more commands!
    splitArguments = event["text"].split(' ', 1)
    command_id = splitArguments[0].lower()

    event["text"] = splitArguments[1] if len(splitArguments) > 1 else ""
    if command_id not in commandsDict:
        return
    func = commandsDict[command_id]
    output = func(event)
    if output:
        print("QOTD Bot says: " + output)




if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Starter Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        bot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            #command, channel = parse_bot_commands(slack_client.rtm_read())
            event = parse_bot_commands(slack_client.rtm_read())
            #if command:
            if event:
               handle_command(event)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")