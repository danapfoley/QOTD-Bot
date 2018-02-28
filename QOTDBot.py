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
DEBUG_CHANNEL = "G9DHWHZP1"
QOTD_CHANNEL = "C9DBNUYNL"

DEPLOY_CHANNEL = QOTD_CHANNEL

LOG_FILE = "log.txt"

# trackers
questionKeeper = QuestionKeeper()
scoreKeeper = ScoreKeeper()

#Commands stuff
#----------------------------------

def say(channel, response):
    try:
        slack_client.api_call(
            "chat.postMessage",
            channel=channel,
            text=response,
            icon_emoji=':robot_face:'
        )
        print("QOTD Bot says: ", response)

        tempfile = NamedTemporaryFile(delete=False)
        with open(LOG_FILE, 'a', newline='') as tempfile:
            tempfile.write("QOTD Bot says: " + response + "\n")
        shutil.move(tempfile.name, LOG_FILE)
    except ValueError:
        print("QOTD Bot failed to say: ", response)



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

def checkPrivate(messageEvent):
    if is_event_private(messageEvent):
        return "You can't suse this command in a private channel. Use the public channel instead"
    else:
        return ""



def help(messageEvent):
    channel, args, userID = messageEvent["channel"], messageEvent["text"], messageEvent["user"]
    response = ""
    if args:
        response += "Not sure what you meant by \"" + args + "\", but here's some help if you need it!\n"

    funcs = []
    for key, func in commandsDict.items():
        if key != "help":
            funcs.append(func)
    funcs = set(funcs) 
    for func in funcs:
        response += func({"type":"message", "channel":channel, "user":userID, "text":"allHelps"}) + "\n"
    
    #sort the responses alphabetically and remove extra stuff
    sortedLines = sorted(response.split('\n'))
    sortedLines = [line for line in sortedLines if line not in ["","\n"]]
    response = '\n\n'.join(sortedLines)

    say(channel, "Here's a list of commands I know:\n" + response)
    return response

def scores(messageEvent):
    channel, args = messageEvent["channel"], messageEvent["text"].split(' ', 1)
    response = ""

    if len(args) > 0 and args[0] != "":
        if args[0] == "help":
            response += "Usage:\n"
        if args[0] in ["help", "usage", "allHelps"]:
            response += "`scores <@ user>` - prints a list of today's scores and running totals, for `<@ user>` if given, for everyone otherwise"
        if args[0] == "allHelps":
            return response

        if response != "":
            say(channel, response)
            return response

        userID = args[0]
        for char in "<>@":
            userID = userID.replace(char, "")
        userID = userID.strip()
        print(userID)
        if getNameByID(userID) != userID: #if user name is valid
            response = scoreKeeper.getUserScores(userID)
        else:
            response = "I couldn't find that user. Use `scores help` for usage instructions"
        
        say(channel, response)
        return response
    if response != "":
        say(channel, response)
        return response
    

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
    if identifier in ["help", "usage", "allHelps"]:
        response += "`question [identifier] [question] : <answer>` - creates a question with a reference tag `identifier`.\n"\
            +  "`question [identifier] remove` - removes the question with the corresponding ID.\n"
    if identifier == "allHelps":
        return response
    if response != "":
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
            print(channel)
            print(response)
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
    channel, args = messageEvent["channel"], messageEvent["text"].split(' ', 1)

    response = ""

    if len(args) > 0:
        if args[0] == "help":
            response += "Usage:\n"
        if args[0] in ["help", "usage", "allHelps"]:
            response += "`questions` - prints a list of today's published questions"
        if args[0] == "allHelps":
            return response
    if response != "":
        say(channel, response)
        return response
    
    response = questionKeeper.listQuestions()

    if response == "":
        response = "There are no currently active questions"
    else:
        response = "Here are all the currently active questions:\n" + response
    
    say(channel, response)
    return response

def myQuestions(messageEvent):
    channel, args, userID = messageEvent["channel"], messageEvent["text"].split(' ', 1), messageEvent["user"]

    response = ""

    if len(args) > 0:
        if args[0] == "help":
            response += "Usage:\n"
        if args[0] in ["help", "usage", "allHelps"]:
            response += "`my-questions` - prints a list of your questions, published or not"
        if args[0] == "allHelps":
            return response
    if response != "":
        say(channel, response)
        return response

    response = checkPublic(messageEvent)
    if response != "":
        say(channel, response)
        return response
    
    response = questionKeeper.listQuestionsByUser(userID)

    if response == "":
        response = "You have no questions right now. Use `question` to add some"
    else:
        response = "Here are all of your questions:\n" + response
    
    say(channel, response)
    return response

def publish(messageEvent):
    channel = messageEvent["channel"]

    args = messageEvent["text"].split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    response = ""

    if identifier == "help":
        response += "Usage: "
    if identifier in ["help", "usage", "allHelps"]:
        response += "`publish <identifier>` - publishes the corresponding question if `identifier` given. "\
            + "Publishes all of your questions otherwise.\n"
    if identifier == "allHelps":
        return response
    if response != "":
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
        say(DEPLOY_CHANNEL, "New questions:\n" + newQuestions)

    say(channel, response)
    return response
    
def answer(messageEvent):
    channel, userID = messageEvent["channel"], messageEvent["user"]

    args = messageEvent["text"].split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    response = ""
    
    if identifier == "help":
        response += "Usage: "
    if identifier in ["help", "usage", "allHelps"]:
        response += "`answer [identifier] [your answer]` - Must be used in a private channel. "\
            + "Checks your `answer` for the corresponding question.\n"
    if args[0] == "allHelps":
            return response
    if response != "":
        say(channel, response)
        return response
    if len(args) < 2:
        response = "This command needs more arguments! Type \"answer help\" for usage"
        say(channel, response)
        return response

    response = checkPublic(messageEvent)
    if response != "":
        say(channel, response)
        return response
    
    inputAnswer = args[1] #no longer holding identifier
    checkResponse = questionKeeper.checkAnswer(messageEvent["user"], identifier, inputAnswer)

    if checkResponse == "correct":
        response = "Correct! I'll give you a point\n"
        messageEvent["text"] = messageEvent["user"]
        addPoint(messageEvent, identifier)
    elif checkResponse == "incorrect":
        q = questionKeeper.getQuestionByID(identifier)
        guessesLeft = MAX_GUESSES - q.guesses[userID]
        response = "Incorrect. You have " + str(guessesLeft) + (" guesses left.\n" if guessesLeft != 1 else " guess left.\n")
        if guessesLeft == 0:
            response += "The correct answer was \"" + q.correctAnswer + "\". If you think your guess(es) should have been correct, contact @" \
                + getNameByID(q.userID) + ", who submitted the question.\n" 
    elif checkResponse == "already answered":
        response = "You already answered that question!"
    elif checkResponse == "max guesses":
        response = "You've already guessed the maximum number of times, " + str(MAX_GUESSES) + "."
    elif checkResponse == "needsManual":
        userWhoSubmitted = questionKeeper.getSubmitterByQID(identifier)
        response = "This question needs to be validated manually. I'll ask " + getNameByID(userWhoSubmitted) + " to check your answer."
        directUserChannel = getDirectChannel(userWhoSubmitted)
        say(directUserChannel, getNameByID(userID) + " has answered \"" + inputAnswer + "\" for your question,\n" + questionKeeper.getQuestionByID(identifier).prettyPrint() \
            + "\nIs this correct?\n(I don't know how to validate answers this way yet)")
    else:
        response = "I couldn't find a question with that ID.\n Use `questions` to find the proper ID.\n"

    say(channel, response)
    return response

def hello(messageEvent):
    channel, args, userID = messageEvent["channel"], messageEvent["text"].split(' '), messageEvent["user"]

    response = ""

    if len(args) > 0:
        if args[0] == "help":
            response += "Usage:\n"
        if args[0] in ["help", "usage", "allHelps"]:
            response += "`hello` - says hi back and some basic information"
    if args[0] == "allHelps":
            return response
    if response != "":
        say(channel, response)
        return response


    userName = getNameByID(userID)

    response = "Hello " + userName + ", I'm QOTD Bot!"
    response += "\nYour User ID is: " + userID + "\nThis channel's ID is: " + channel + "\nUse the `help` command for usage instructions.\n"
    say(channel, response)

def addPoint(messageEvent, qID = ""):
    channel, args, userID = messageEvent["channel"], messageEvent["text"].split(' '), messageEvent["user"]

    response = ""

    if len(args) > 0:
        refID = args[0]
        if refID == "help":
            response += "Usage:\n"
        if refID in ["help", "usage", "allHelps"]:
            response += "`add-point <user>` - gives a point to <user> if given, gives a point to you if left blank"
        if refID == "allHelps":
            return response
        if response != "":
            say(channel, response)
            return response
        
        for char in "<>@":
            refID = refID.replace(char, "")
        refID = refID.strip()
        if getNameByID(refID) != refID: #if user name is valid
            userID = refID
        else:
            response = "I couldn't find that user. Use `add-point help` for usage instructions"
            say(channel, response)
            return response

    if not scoreKeeper.userExists(userID):
        scoreKeeper.addNewUser(userID)
        scoreKeeper.addNameToUser(userID, getNameByID(userID))
    scoreKeeper.addUserPoint(userID)

    say(DEPLOY_CHANNEL, "Point for " + getNameByID(userID) + ((" on question " + qID + "!") if qID != "" else "!"))

def addPoints(messageEvent):
    channel = messageEvent["channel"]

    args = messageEvent["text"].split(' ', 1)

    if len(args) < 1 or args[0] == "":
        response = "This command needs more arguments! Type \"add-points help\" for usage"
        say(channel, response)
        return response

    userID = args[0]
    numPoints = args[1] if len(args) >= 2 else 1

    response = ""

    if userID == "help":
        response += "Usage: "
    if userID in ["help", "usage", "allHelps"]:
        response += "`add-point(s) [@ user] <# points>` "\
        + "- gives `# points` to `@ user` if specified, 1 point by default\n"
    if userID == "allHelps":
        return response
    if response != "":
        say(channel, response)
        return response

    response = checkPrivate(messageEvent)
    if response != "":
        say(channel, response)
        return response

    for char in "<>@":
        userID = userID.replace(char, "")
    userID = userID.strip()
    if getNameByID(userID) == userID: #if user name is invalid
        response = "I couldn't find that user. Use `add-point help` for usage instructions"
        say(channel, response)
        return response

    if not scoreKeeper.userExists(userID):
        scoreKeeper.addNewUser(userID)
        scoreKeeper.addNameToUser(userID, getNameByID(userID))
    scoreKeeper.addUserPoints(userID, int(numPoints.replace(",","")))

    response = "Okay, I gave " + str(numPoints) + " point" + ("s" if numPoints != 1 else "") + " to " + getNameByID(userID)
    say(DEPLOY_CHANNEL, response)
    return response

def channelID(messageEvent):
    channel, args, userID = messageEvent["channel"], messageEvent["text"].split(' '), messageEvent["user"]

    response = ""

    if len(args) > 0:
        if args[0] == "help":
            response += "Usage:\n"
        if args[0] in ["help", "usage", "allHelps"]:
            response += "`channel-id` - gets the id of the current channel. Used for debugging"
        if args[0] == "allHelps":
            return response
    if response != "":
        say(channel, response)
        return response

    response = "The channel we're in now is: " + channel
    say(channel, response)
    return response

def expireOldQuestions(messageEvent):
    channel, args, userID = messageEvent["channel"], messageEvent["text"].split(' '), messageEvent["user"]

    response = ""

    if len(args) > 0:
        if args[0] == "help":
            response += "Usage:\n"
        if args[0] in ["help", "usage", "allHelps"]:
            response += "`expire-old-questions` - removes all questions published more than 24 hours ago"
        if args[0] == "allHelps":
            return response
    if response != "":
        say(channel, response)
        return response

    expiredQuestions = questionKeeper.expireQuestions(userID)
    if len(expiredQuestions) > 0:
        response = "The following questions have expired:\n"
        response += '\n'.join(expiredQuestions)
        say(DEPLOY_CHANNEL, response)
    else:
        response = "No questions of yours older than 24 hours were found"

    say(channel, response)
    return response


commandsDict = {
    "help" : help,
    "scores" : scores,
    "score" : scores,
    "points" : scores,
    "question" : question,
    "q" : question,
    "questions" : questions,
    "qs" : questions,
    "my-questions" : myQuestions,
    "publish" : publish,
    "answer" : answer,
    "a" : answer,
    "hello" : hello,
    "hi" : hello,
    "hola" : hello,
    "add-point" : addPoints,
    "add-points" : addPoints,
    "channel-id" : channelID,
    "expire-old-questions" : expireOldQuestions
}

def tell(messageEvent):
    channel, args, originUserID = messageEvent["channel"], messageEvent["text"].split(' ', 1), messageEvent["user"]

    response = ""

    if len(args) > 0:
        if args[0] == "help":
            response += "Usage:\n"
        if args[0] in ["help", "usage", "allHelps"]:
            response += "`tell [@user] [message]` - tells a user something"
        if args[0] == "allHelps":
            return response
    if len(args) < 2:
        response = "this command needs more arguments!"
    if response != "":
        say(channel, response)
        return response

    userID = args[0]

    for char in "<>@":
        userID = userID.replace(char, "")

    userID = userID.strip()
    userName = getNameByID(userID)
    if userName == userID: #if user name is invalid
        response = "I couldn't find that user. Use `add-point help` for usage instructions"
        say(channel, response)
        return response

    response = userName + ", " + getNameByID(originUserID) + " says " + args[1]

    say(DEPLOY_CHANNEL, response)
    return response


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
        if event["type"] == "error":
            print("Network error. Retrying in 5 seconds...\n")
            time.sleep(5)
            return None
        if event["type"] == "message" and not "subtype" in event:
            processedEvent = parse_direct_mention(event)
            if processedEvent:
                print(getNameByID(event["user"]) + " says: " + event["text"])
                tempfile = NamedTemporaryFile(delete=False)
                with open(LOG_FILE, 'a', newline='') as tempfile:
                    tempfile.write(getNameByID(event["user"]) + " says: " + event["text"] + "\n")
                shutil.move(tempfile.name, LOG_FILE)
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
    if command_id == "say-shutdown":
        say(DEPLOY_CHANNEL, "Shutting down for a while. Beep boop.")
    if command_id == "say-startup":
        say(DEPLOY_CHANNEL, "Starting up for the day! Beep boop.")
    if command_id == "say-downtime":
        say(DEPLOY_CHANNEL, "Sorry, I was down for a bit! Be sure to re-send any questions you entered that I didn't respond to.")
    if command_id in ["tell", "say", "trash-talk"]:
        tell(event)
    if command_id not in commandsDict:
        return
    func = commandsDict[command_id]
    func(event)



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