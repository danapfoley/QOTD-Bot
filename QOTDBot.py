import random
import traceback

from WellBehavedSlackClient import *

from QuestionKeeper import *
from ScoreKeeper import *
from PollKeeper import *
from MessageReactionMonitor import *

#Make keeper objects global. They are initialized in main
slackClient = None
questionKeeper = None
scoreKeeper = None
commandKeeper = None
pollKeeper = None
messageReactionMonitor = None


#Add more responses here to be randomly picked
POINT_RESPONSES = ["Correct! I'll give you a point", ":thumbsup:", "Correct! :fast_parrot:"]


def getNameByID(userID):
    # All Slack user IDs start with "U" or "W", by convention
    # So this is an easy check for invalid names
    if not (userID.startswith('U') or userID.startswith('W')):
        return userID

    #Our top priority is to get the name from the score sheet,
    #since we can change that to a person's preference if they don't want to use their display name
    nameFromScoreSheet = scoreKeeper.getUserNameInScoreSheet(userID)
    if nameFromScoreSheet:
        userName = nameFromScoreSheet
        return userName

    # Otherwise, we try the cached user list, and as a last resort, do an API call
    return slackClient.getNameByID(userID)


def needsMoreArgs(channel):
    slackClient.say(channel, "This command needs more arguments! Type \"(command) help\" for usage")

def scores(channel, userID, argsString, timestamp):
    """
    Print a list of today's scores, and running monthly scores
    Ranked by number of points
    """
    args = argsString.split(' ', 1)

    #If a user to get scores for is specified
    if len(args) > 0 and args[0] != "":
        scoresForUser = getIDFromReference(args[0])
        
        if getNameByID(scoresForUser) != scoresForUser: #if user name is valid
            response = scoreKeeper.getUserScores(scoresForUser)
        else:
            response = "I couldn't find that user. Use `scores help` for usage instructions"
        
        slackClient.say(channel, response)
        return

    #Otherwise, print scores for everyone
    response = scoreKeeper.getTodayScoresRanked()
    response += scoreKeeper.getTotalScoresRanked()
    slackClient.say(channel, response)

def scoresUnranked(channel, userID, argsString, timestamp):
    """
    Print a list of today's scores, and running monthly scores
    Sorted alphabetically
    """
    response = scoreKeeper.getTodayScores()
    response += scoreKeeper.getTotalScores()
    slackClient.say(channel, response)

def question(channel, userID, argsString, timestamp):
    """
    Add or modify a new question
    """
    argsString = argsString.replace("“", "\"").replace("”", "\"")

    if argsString == "":
        needsMoreArgs(channel)
        return

    category = ""
    if argsString[0] == "\"":
        secondQuoteIdx = argsString.find("\"", 1)
        if secondQuoteIdx != -1:
            category = argsString[0:secondQuoteIdx]
            argsString = argsString[secondQuoteIdx:]

    args = argsString.split(' ', 1)

    identifier = (category + args[0]) if len(args) > 0 else ""

    response = ""

    if identifier == "remove":
        response = "You probably meant to use `question [identifier] remove`\n"
        slackClient.say(channel, response)
        return

    if len(args) < 2:
        needsMoreArgs(channel)
        return
    args = args[1].split(" : ") #no longer holding identifier
    #args should now look like: "question text : answer1 : answer2 : ..."
    #   or "question text"

    if len(args) < 1:
        needsMoreArgs(channel)
        return
    else:
        answers = []

    question = args[0].strip()

    if len(args) > 1:
        answers = [answer.strip() for answer in args[1:]]
    else:
        answers = []

    if question == "remove":
        if questionKeeper.removeQuestion(identifier, "DEV" if userID == DEVELOPER_ID else userID):
            response = "Okay, I removed that question"
            slackClient.say(channel, response)
            return
        else:
            response = "I couldn't find a question of yours with that ID"
            slackClient.say(channel, response) 
            return

    if question == "count":
        q = questionKeeper.getUserQuestionByID(identifier, "DEV" if userID == DEVELOPER_ID else userID)

        if q is None:
            response = "I couldn't find a question of yours with that ID"
            slackClient.say(channel, response)
            return

        numAnswers = q.countAnswers()
        numGuesses = q.countGuesses()

        response = str(numAnswers) + (" people" if numAnswers != 1 else " person") + " answered question " + q.qID + " correctly"

        if numAnswers > 0:
            response += ":\n"
            response += "\n".join([("-" + getNameByID(answeredByID)) for answeredByID in q.answeredBy])

        response += "\n\n"
        response += str(numGuesses) + (" people" if numGuesses != 1 else " person") + " guessed " + q.qID \
                 + ", and " + str(numGuesses - numAnswers) + " didn't guess the right answer"

        if (numGuesses - numAnswers) > 0:
            response += ":\n"
            response += "\n".join([("-" + getNameByID(guessedID)) for guessedID in q.guesses.keys() if guessedID not in q.answeredBy])

        slackClient.say(channel, response)
        return


    #only get here if a valid question input format is given
    questionAdded = questionKeeper.addQuestion(userID = userID, qID = identifier, questionText = question, correctAnswers = answers)

    if questionAdded:
        response = "Okay, I added your question with ID " + identifier + ".\n"\
                 + "Use `publish` to make your questions publicly available, "\
                 + "or `question " + identifier + " remove` to remove it"
        slackClient.say(channel, response)
        if answers == []:
            slackClient.say(channel, "Warning: Your question doesn't seem to have a correct answer. Make sure this is intended before publishing.")
    else:
        response = "A question with this ID already exists right now. Please use a different one"
        slackClient.say(channel, response)

def addAnswer(channel, userID, argsString, timestamp):
    """
    Add a possible answer to an existing question
    """
    argsString = argsString.replace("“", "\"").replace("”", "\"")

    if argsString == "":
        needsMoreArgs(channel)
        return

    category = ""
    if argsString[0] == "\"":
        secondQuoteIdx = argsString.find("\"", 1)
        if secondQuoteIdx != -1:
            category = argsString[0:secondQuoteIdx]
            argsString = argsString[secondQuoteIdx:]

    args = argsString.split(' ', 1)

    identifier = (category + args[0]) if len(args) > 0 else ""

    if len(args) < 2:
        needsMoreArgs(channel)
        return
    args = args[1].split(" : ")  # no longer holding identifier
    # args should now look like: "[answer1, answer2, ...]"
    #   or just "[answer1]"

    if len(args) < 1:
        needsMoreArgs(channel)
        return

    args = [arg.strip() for arg in args]

    for newAnswer in args:
        if not questionKeeper.addAnswer(userID, identifier, newAnswer):
            slackClient.say(channel, "I couldn't find a question of yours with that ID.\n")
            return

    if len(args) > 1:
        slackClient.say(channel, "Okay, I added the answers \"" + "\", \"".join(args) + "\" to your question " + identifier)
    else:
        slackClient.say(channel, "Okay, I added the answer \"" + args[0] + "\" to your question " + identifier)

def removeAnswer(channel, userID, argsString, timestamp):
    """
    Remove an answer option from an existing question. Must match the existing answer string exactly
    """
    argsString = argsString.replace("“", "\"").replace("”", "\"")

    if argsString == "":
        needsMoreArgs(channel)
        return

    category = ""
    if argsString[0] == "\"":
        secondQuoteIdx = argsString.find("\"", 1)
        if secondQuoteIdx != -1:
            category = argsString[0:secondQuoteIdx]
            argsString = argsString[secondQuoteIdx:]

    args = argsString.split(' ', 1)

    identifier = (category + args[0]) if len(args) > 0 else ""

    if len(args) < 2:
        needsMoreArgs(channel)
        return

    existingAnswer = args[1].strip() #no longer holding identifier

    q = questionKeeper.getUserQuestionByID(identifier, userID)
    if not q:
        slackClient.say(channel, "I couldn't find a question of yours with that ID.\n")
        return
    if not questionKeeper.removeAnswer(userID, identifier, existingAnswer):
        slackClient.say(channel, "I couldn't find an answer that matches your input.\n The current answers are: " + ", ".join(q.correctAnswers) + "\n Try again with one of those\n")
        return

    slackClient.say(channel, "Okay, I removed the answer \"" + existingAnswer + "\" from your question " + identifier)

def questions(channel, userID, argsString, timestamp):
    """
    List all currently active questions.
    If used in a private channel, the list will include bullet points next to unanswered questions
    """
    if isChannelPrivate(channel):
        response = questionKeeper.listQuestionsPrivate(userID)
    else:
        response = questionKeeper.listQuestions()

    if response == "":
        response = "There are no currently active questions"
    else:
        response = "Here are all the currently active questions:\n" + response
    
    slackClient.say(channel, response)


def questionsRemaining(channel, userID, argsString, timestamp):
    """
    Similar to `questions`, but any question that has already been answered,
        guessed the max number of times, or was submitted by you, is omitted.
    """
    response = questionKeeper.listIncompleteQuestionsPrivate(userID)

    if response == "":
        response = "There are no currently active questions that you can answer"
    else:
        response = "Here are all the currently active questions you have yet to get correct or use all your guesses on:\n" + response

    slackClient.say(channel, response)

def removeQuestion(channel, userID, argsString, timestamp):
    """
    Remove an question, published or not.
    Questions that are removed and not expired do not get saved in question history
    """
    if argsString == "":
        needsMoreArgs(channel)
        return

    args = argsString.split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    question(channel, userID, identifier + " remove", timestamp)


def myQuestions(channel, userID, argsString, timestamp):
    """
    List all questions you've submitted, published or not.
    Includes answers, and thus must be used in a private channel
    """
    args = argsString.split(' ', 1)

    response = questionKeeper.listQuestionsByUser(userID)

    if response == "":
        response = "You have no questions right now. Use `question` to add some"
    else:
        response = "Here are all of your questions:\n" + response
    
    slackClient.say(channel, response)

def publish(channel, userID, argsString, timestamp):
    """
    Publish all questions by a user.
    If question ID given as argument, publish only that question
    """
    args = argsString.split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    if identifier != "":
        publishResponse = questionKeeper.publishByID(identifier)
        if publishResponse == "published":
            response = "Okay, I published question " + identifier + ".\n"
        elif publishResponse == "already published":
            response = identifier + " is already published.\n"
        else:
            response = "I couldn't find a question with that ID.\n"
    else:
        questionKeeper.publishAllByUser(userID)
        response = "Okay, I've published all of your questions\n"

    newQuestions = questionKeeper.firstTimeDisplay()
    if newQuestions != "":
        slackClient.say(DEPLOY_CHANNEL, "New questions:\n" + newQuestions)

    slackClient.say(channel, response)
    
def answer(channel, userID, argsString, timestamp):
    """
    Guess the answer to a question.
    Checks for correctness, number of guesses,
        and whether or not to validate manually
    """
    args = argsString.split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    if len(args) < 2:
        needsMoreArgs(channel)
        return

    inputAnswer = args[1] #no longer holding identifier
    checkResponse = questionKeeper.checkAnswer(userID, identifier, inputAnswer)

    if checkResponse == "correct":
        qID = questionKeeper.getQuestionByID(identifier).qID #Calling this to get proper capitalization
        response = random.choice(POINT_RESPONSES) + "\n"

        if not scoreKeeper.userExists(userID):
            scoreKeeper.addNewUser(userID)
            scoreKeeper.addNameToUser(userID, getNameByID(userID))

        scoreKeeper.addUserPoint(userID)
        slackClient.say(POINT_ANNOUNCEMENT_CHANNEL, "Point for " + getNameByID(userID) + ((" on question " + qID + "!") if qID != "" else "!") \
                            + ("\nThough they are the one who submitted it :wha:..." if userID == questionKeeper.getSubmitterByQID(qID) else ""))

    elif checkResponse == "incorrect":
        q = questionKeeper.getQuestionByID(identifier)
        guessesLeft = MAX_GUESSES - q.guesses[userID]
        response = "Incorrect. You have " + str(guessesLeft) + (" guesses left.\n" if guessesLeft != 1 else " guess left.\n")
        if guessesLeft == 0:
            response += ("The correct answers allowed were " if len(q.correctAnswers) > 1 else "The correct answer was ") \
                     + ", ".join("\"" + a + "\"" for a in q.correctAnswers) + ". If you think your guess(es) should have been correct, contact " \
                     +  getReferenceByID(q.userID) + ", who submitted the question.\n"

    elif checkResponse == "gave up":
        q = questionKeeper.getQuestionByID(identifier)
        response = ("The correct answers allowed were " if len(q.correctAnswers) > 1 else "The correct answer was ") \
                    + ", ".join("\"" + a + "\"" for a in
                                q.correctAnswers) + ". If you think your guess(es) should have been correct, contact " \
                    + getReferenceByID(q.userID) + ", who submitted the question.\n"

    elif checkResponse == "already answered":
        response = "You already answered that question!"

    elif checkResponse == "max guesses":
        response = "You've already guessed the maximum number of times, " + str(MAX_GUESSES) + "."

    elif checkResponse == "needs manual":
        userWhoSubmitted = questionKeeper.getSubmitterByQID(identifier)
        response = "This question needs to be validated manually. I'll ask " + getNameByID(userWhoSubmitted) + " to check your answer."
        directUserChannel = slackClient.getDirectChannel(userWhoSubmitted)
        apiResponse = slackClient.say(directUserChannel, getNameByID(userID) + " has answered \"" + inputAnswer + "\" for your question,\n" + questionKeeper.getQuestionByID(identifier).prettyPrint() \
            + "\nIs this correct?\nReact to this message with :+1: to give them a point.")

        if apiResponse is not None and "ts" in apiResponse:
            messageReactionMonitor.addMonitoredMessage(channel, userID, apiResponse["ts"], {"qID" : identifier, "pointForUser" : userID}, "manual answer")

    else:
        response = "I couldn't find a question with that ID.\n Use `questions` to find the proper ID.\n"

    slackClient.say(channel, response)

def oldQuestions(channel, userID, argsString, timestamp):
    """
    List all questions that were expired less than 24 hours ago.
    Does not include questions that were removed
    """
    response = questionKeeper.getOldQuestionsString()

    if response != "":
        response = "Here are all of the questions I found that were expired in the last 24 hours:\n\n" + response
    else:
        response = "I couldn't find any questions that were expired in the last 24 hours"
    slackClient.say(channel, response)

def hello(channel, userID, argsString, timestamp):
    """
    Say hi and some basic ID info
    """
    response = "Hello " + getNameByID(userID) + ", I'm QOTD Bot!"
    response += "\nYour User ID is: " + userID + "\nThis channel's ID is: " + channel + "\nUse the `help` command for usage instructions.\n"
    
    slackClient.say(channel, response)

def addPoints(channel, userID, argsString, timestamp):
    """
    Add a number of points for a mentioned user
    """
    args = argsString.split(' ')

    if len(args) < 1 or args[0] == "":
        needsMoreArgs(channel)
        return

    pointsForUser = getIDFromReference(args[0])
    numPoints = args[1] if len(args) >= 2 and args[1] != "" else "1"

    if getNameByID(pointsForUser) == pointsForUser: #if user name is invalid
        slackClient.say(channel, "I couldn't find that user. Use `add-point help` for usage instructions")
        return

    #Get a string of just digits
    numPointsDigitsOnly = "".join([c for c in numPoints if c.isdigit()])
    #Add back in a negative sign if one was given
    if numPoints != "" and numPoints[0] == "-" and numPointsDigitsOnly != "":
        numPointsDigitsOnly = "-" + numPointsDigitsOnly

    if numPointsDigitsOnly == "":
        slackClient.say(channel, "I couldn't interpret " + numPoints + " as a number. Try again\n")
        return

    if not scoreKeeper.userExists(userID):
        scoreKeeper.addNewUser(userID)
        scoreKeeper.addNameToUser(userID, getNameByID(userID))

    numPointsDigitsOnly = int(numPointsDigitsOnly)
    scoreKeeper.addUserPoints(pointsForUser, numPointsDigitsOnly)

    response = "Okay, I gave " + str(numPointsDigitsOnly) + " point" + ("s" if numPointsDigitsOnly != 1 else "") + " to " + getNameByID(pointsForUser)
    slackClient.say(DEPLOY_CHANNEL, response)

def expireOldQuestions(channel, userID, argsString, timestamp):
    """
    Expire all questions of yours older than 18 hours.
    Posts the expired questions, their answers,
        and a list of users who answered correctly, to the deploy channel.
    """
    expiredQuestions = questionKeeper.expireQuestions(userID)
    expiredQuestionsStrings = []
    for q in expiredQuestions:
        expiredQuestionsStrings.append(q.prettyPrintWithAnswer())
        if len(q.getAnsweredUsers()) > 0:
            expiredQuestionsStrings.append("    Answered by:")
        for answeredUserID in q.getAnsweredUsers():
            expiredQuestionsStrings.append("        -" + getNameByID(answeredUserID))
        expiredQuestionsStrings.append("\n")

    if len(expiredQuestions) > 0:
        response = "The following questions have expired:\n"
        response += '\n'.join(expiredQuestionsStrings)
        if channel != DEPLOY_CHANNEL:
            slackClient.say(DEPLOY_CHANNEL, response)
    else:
        response = "No questions of yours older than 18 hours were found"

    slackClient.say(channel, response)

def poll(channel, userID, argsString, timestamp):
    """
    Create or modify a poll, with poll text and options separated by " : "
    """
    if argsString == "":
        needsMoreArgs(channel)
        return

    args = argsString.split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    response = ""

    if identifier == "remove":
        response = "You probably meant to use `poll [identifier] remove`\n"
        slackClient.say(channel, response)
        return

    if len(args) < 2:
        needsMoreArgs(channel)
        return

    args = args[1].split(" : ") #no longer holding identifier, question and options split
    question = args[0]
    optionsList = args[1:]

    optionsDict = {}
    for i in range(len(optionsList)):
        optionsDict[str(i+1)] = optionsList[i]

    if question == "remove":
        if pollKeeper.removePoll(identifier, "DEV" if userID == DEVELOPER_ID else userID):
            response = "Okay, I removed that poll"
            slackClient.say(channel, response)
            return
        else:
            response = "I couldn't find a poll of yours with that ID"
            slackClient.say(channel, response) 
            return

    if question in ["votes", "status", "results", "check"]:
        response = pollKeeper.displayResults(identifier)
        if response is None:
            response = "I couldn't find a poll with that ID"
        slackClient.say(channel, response) 
        return



    #only get here if a valid poll input format is given
    pollAdded = pollKeeper.addPoll(userID = userID, pID = identifier, pollQuestionText = question, options = optionsDict)

    if pollAdded:
        response = "Okay, I added your poll with ID " + identifier + ".\n"\
                 + "It looks like this:\n\n\n" + pollKeeper.getPollByID(identifier).prettyPrint() + "\n\n\n"\
                 + "Use `publish-poll` to make your poll publicly available, "\
                 + "or `poll " + identifier + " remove` to remove it"
    else:
        response = "A poll with this ID already exists right now. Please use a different one"

    slackClient.say(channel, response)

def polls(channel, userID, argsString, timestamp):
    """
    List all currently active polls
    """
    args = argsString.split(' ', 1)

    response = pollKeeper.listPolls()

    if response == "":
        response = "There are no currently active polls"
    else:
        response = "Here are all the currently active polls:\n" + response
    
    slackClient.say(channel, response)

def publishPoll(channel, userID, argsString, timestamp):
    """
    Publish all of your polls
    If ID given, publish only the poll with that ID
    """
    args = argsString.split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    if identifier != "":
        publishResponse = pollKeeper.publishByID(identifier)
        if publishResponse == "published":
            response = "Okay, I published poll " + identifier + ".\n"
        elif publishResponse == "already published":
            response = identifier + " is already published.\n"
        else:
            response = "I couldn't find a poll with that ID.\n"
    else:
        pollKeeper.publishAllByUser(userID)
        response = "Okay, I've published all of your polls\n"

    newPolls = pollKeeper.firstTimeDisplay()
    if newPolls != "":
        slackClient.say(DEPLOY_CHANNEL, "New polls:\n" + newPolls)

    slackClient.say(channel, response)

def respondToPoll(channel, userID, argsString, timestamp):
    """
    Vote on a poll.
    Identifier must match poll ID, and the vote must match the corresponding number of the option
    """
    args = argsString.split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    if len(args) < 2:
        needsMoreArgs(channel)
        return

    inputVote = args[1] #no longer holding identifier
    checkVote = pollKeeper.submitResponse(userID, identifier, inputVote)

    if checkVote == "not found":
        response = "I couldn't find a poll with that ID.\n"
        slackClient.say(channel, response)
        return

    if checkVote == "bad vote":
        response = "I couldn't find an option that matches \"" + identifier + "\".\n"
        slackClient.say(channel, response)
        return
    
    slackClient.react(channel, timestamp, "thumbsup")

def tell(channel, userID, argsString, timestamp):
    """
    Make the bot talk to another user, in the deploy channel.
    The user who says the command is not hidden
    """
    args = argsString.split(' ', 1)

    response = ""

    if len(args) < 2:
        #Not using the needsMoreArgs function since this is a hidden command and has no help text
        slackClient.say(channel, "this command needs more arguments!")
        return

    userToTell = getIDFromReference(args[0])
    whatToSay = args[1]

    if getNameByID(userToTell) == userToTell: #if user name is invalid
        slackClient.say(channel, "I couldn't find that user. Use `add-point help` for usage instructions")
        return

    slackClient.say(DEPLOY_CHANNEL, "Hey " + getReferenceByID(userID) + ", " + getReferenceByID(userID) + " says " + whatToSay)

def devTell(channel, userID, argsString, timestamp):
    """
    Make the bot speak on behalf of the dev, in a direct chat with a user
    """
    args = argsString.split(' ', 1)

    response = ""

    if len(args) < 2:
        #Not using the needsMoreArgs function since this is a hidden command and has no help text
        slackClient.say(channel, "this command needs more arguments!")
        return

    userToTell = getIDFromReference(args[0])
    whatToSay = args[1]

    if getNameByID(userToTell) == userToTell: #if user name is invalid
        slackClient.say(channel, "I couldn't find that user. Use `add-point help` for usage instructions")
        return

    userChannel = slackClient.getDirectChannel(userToTell)

    slackClient.say(userChannel, whatToSay)

def announce(channel, userID, argsString, timestamp):
    """
    Make the bot speak on behalf of the dev, to the deploy channel
    """
    slackClient.say(DEPLOY_CHANNEL, argsString)

def refreshUserList(channel, userID, argsString, timestamp):
    """
    Update the user list that caches user name info
    """
    usersJson = {}

    usersList = slackClient.api_call("users.list")["members"]
    for member in usersList:
        name = member["profile"]["display_name"]
        if name == "":
            name = member["profile"]["real_name"]
        usersJson[member["id"]] = name

    tempfile = NamedTemporaryFile(delete=False)
    with open(USER_LIST_FILE, 'w') as tempfile:
        json.dump(usersJson, tempfile, indent = 4)

    shutil.move(tempfile.name, USER_LIST_FILE)


class Command:
    def __init__(self, aliases, func, category = "", helpText = "", publicOnly = False, privateOnly = False, devOnly = False):
        self.aliases = aliases
        self.func = func
        self.category = category
        self.helpText = helpText
        self.publicOnly = publicOnly
        self.privateOnly = privateOnly
        self.devOnly = devOnly


class CommandKeeper:
    def __init__(self):
        self.helpTextDict = {"Misc" : []}
        self.commandsList = [
            Command(
                aliases = ["points","score","scores"],
                func = scores,
                category = "Scoring and Points",
                helpText = "`scores <@ user>` - prints a list of today's scores and running totals, for `<@ user>` if given, for everyone otherwise"
            ),

            Command(
                aliases = ["score-unranked","scores-unranked"],
                func = scoresUnranked,
                category = "Scoring and Points",
                helpText = "`scores-unranked` - prints a list of today's scores and running totals, sorted alphabetically instead of by ranking"
            ),

            Command(
                aliases = ["q","question"],
                func = question,
                category = "Questions and Answers",
                helpText = "`question [identifier] [question] : <answer1> : <answer2> : ...` - creates a question with a reference tag `identifier`.\n"\
                         + "`question [identifier] remove` - removes the question with the corresponding ID.\n"\
                         + "`question [identifier] count` - shows stats on who has answered/guessed a question.",
                privateOnly = True
            ),

            Command(
                aliases = ["add-answer","add-answers"],
                func = addAnswer,
                category = "Questions and Answers",
                helpText = "`add-answer  [identifier] [new answer]` - adds a new possible answer for the question with the corresponding identifier.\n"\
                         + "`add-answers [identifier] [new answer 1] : <new answer 2> : ...` - adds multiple new answers for the question with the corresponding identifier",
                privateOnly = True
            ),

            Command(
                aliases=["remove-answer"],
                func = removeAnswer,
                category="Questions and Answers",
                helpText="`remove-answer [identifier] [existing answer]` - removes an answer option from a question. Must be matched _exactly_ to work",
                privateOnly=True
            ),

            Command(
                aliases = ["qs", "questions"],
                func = questions,
                category = "Questions and Answers",
                helpText = "`questions` - prints a list of today's published questions"
            ),

            Command(
                aliases = ["questions-remaining"],
                func = questionsRemaining,
                category = "Questions and Answers",
                helpText = "`questions-remaining` - Prints a list of questions that you have yet to answer or use all your guesses on"
            ),

            Command(
                aliases = ["rq", "remove", "remove-question"],
                func = removeQuestion,
                category = "Questions and Answers",
                helpText = "`remove [identifier]` removes the question with the corresponding ID"
            ),

            Command(
                aliases = ["my-questions"],
                func = myQuestions,
                category = "Questions and Answers",
                helpText = "`my-questions` - prints a list of your questions, published or not"
            ),

            Command(
                aliases = ["publish"],
                func = publish,
                category = "Questions and Answers",
                helpText = "`publish <identifier>` - publishes the corresponding question if `identifier` given. "\
                         + "Publishes all of your questions otherwise."
            ),

            Command(
                aliases = ["a", "answer"],
                func = answer,
                category = "Questions and Answers",
                helpText = "`answer [identifier] [your answer]` - Must be used in a private channel. "\
                         + "Checks your `answer` for the corresponding question.",
                privateOnly = True
            ),

            Command(
                aliases = ["hi", "hello", "hola"],
                func = hello,
                helpText = "`hello` - says hi back and some basic information"
            ),

            Command(
                aliases = ["add-point", "add-points"],
                func = addPoints,
                category = "Scoring and Points",
                helpText = "`add-point(s) [@ user] <# points>` "\
                         + "- gives `# points` to `@ user` if specified, 1 point by default",
                publicOnly = True
            ),

            Command(
                aliases = ["expire-old-questions"],
                func = expireOldQuestions,
                category = "Questions and Answers",
                helpText = "`expire-old-questions` - removes all questions published more than 18 hours ago"
            ),

            Command(
                aliases = ["old-questions", "expired-questions", "old-answers"],
                func = oldQuestions,
                category = "Questions and Answers",
                helpText = "`old-questions` - gets a list of questions that were expired in the last 24 hours"
            ),

            Command(
                aliases = ["tell", "say", "trash-talk"],
                func = tell
            ),

            Command(
                aliases = ["dev-say", "dev-tell", "dev-talk"],
                func = devTell,
                devOnly = True
            ),

            Command(
                aliases = ["announce"],
                func = announce,
                devOnly = True
            ),

            Command(
                aliases = ["refresh-user-list"],
                func = refreshUserList,
                devOnly = True
            ),

            Command(
                aliases = ["poll", "p"],
                func = poll,
                category = "Polls",
                helpText = "`poll [identifier] [question] : [option 1] : [option 2] : ...` - creates a poll with a reference tag `identifier`.\n"\
                         + "`poll [identifier] remove` - removes the poll with the corresponding ID.\n"\
                         + "`poll [identifier] votes` - shows current vote counts for a poll."
            ),

            Command(
                aliases = ["polls"],
                func = polls,
                category = "Polls",
                helpText = "`polls` - prints a list of the currently active polls"
            ),

            Command(
                aliases = ["publish-poll", "publish-polls"],
                func = publishPoll,
                category = "Polls",
                helpText = "`publish-poll [identifier]` - publishes your poll with the specified identifier"
            ),

            Command(
                aliases = ["respond", "poll-answer", "poll-respond", "answer-poll", "vote"],
                func = respondToPoll,
                category = "Polls",
                helpText = "`vote [identifier] [option-number]` - votes on a poll. Use option IDs, not the option's text"
            )
        ]

        #Categorize help text
        for command in self.commandsList:
            if command.helpText == "":
                continue
            if command.category == "" or command.category == "Misc":
                self.helpTextDict["Misc"].append(command.helpText)
            elif command.category in self.helpTextDict.keys():
                self.helpTextDict[command.category].append(command.helpText)
            else:
                self.helpTextDict[command.category] = [command.helpText]
        for category in self.helpTextDict.keys():
            self.helpTextDict[category].sort()

    def help(self, channel):
        response = ""

        for category in self.helpTextDict:
            response += "*" + category + "*:\n"
            for helpText in self.helpTextDict[category]:
                for line in helpText.split("\n"):
                    response += "    " + line + "\n\n"
            response += "\n\n"
        response = response[:-2]  #Slice off the last two newlines

        slackClient.say(channel, "Here's a list of commands I know:\n\n" + response)

    def getCommandByAlias(self, alias):
        for cmd in self.commandsList:
            if alias in cmd.aliases:
                return cmd
        return None

    def handle_event(self, event):
        """
        Execute bot command if the command is known
        """
        userID = event["user"]
        channel = event["channel"]
        if "ts" in event:
            timestamp = event["ts"]
        else:
            timestamp = 0

        #Clean up multiple whitespace characters for better uniformity for all commands
        #e.g. "This   is:       some text" turns into "This is: some text"
        event["text"] = " ".join(event["text"].split())

        splitArguments = event["text"].split(' ', 1)
        commandAlias = splitArguments[0].lower()

        #This is the result of @qotd_bot help
        if commandAlias == "help":
            self.help(channel)

        cmd = self.getCommandByAlias(commandAlias)
        if not cmd:
            #slackClient.say(channel, "Invalid command")
            return

        if len(splitArguments) > 1:
            #This is the result of @qotd_bot [command] help
            if splitArguments[1] == "help":
                slackClient.say(channel, cmd.helpText)
                return
            
            args = splitArguments[1]  #slice off the command ID, leaving just arguments
        else:
            args = ""


        if cmd.devOnly and userID != DEVELOPER_ID:
            response = "I'm sorry, " + getReferenceByID(userID) + ", I'm afraid I can't let you do that."
            slackClient.say(channel, response)
            return

        if cmd.publicOnly and isChannelPrivate(channel):
            slackClient.say(channel, "You can't use this command in a private channel. Use the public channel instead")
            return

        if cmd.privateOnly and not isChannelPrivate(channel):
            slackClient.say(channel, "You can't use this command in a public channel. Message me directly instead")
            return


        #If we make it through all the checks, we can actually run the corresponding function
        try:
            cmd.func(channel, userID, args, timestamp)
        except Exception as e:
            slackClient.devLog(getNameByID(event["user"]) + " said: " + event["text"] + "\nAnd the following error ocurred:\n\n" + str(e) + "\n\n" + traceback.format_exc())


#----------------------------------

def monitoredMessageCallback(userWhoReacted, emoji, callbackKey, data):

    if callbackKey == "manual answer":
        q = questionKeeper.getQuestionByID(data["qID"])
        if q is None or userWhoReacted != q.userID:
            return False
        if "+1:" not in emoji:
            return False

        qID = q.qID
        pointForUser = data["pointForUser"]

        q.answeredBy.append(pointForUser)
        questionKeeper.writeQuestionsToFile()

        if not scoreKeeper.userExists(pointForUser):
            scoreKeeper.addNewUser(pointForUser)
            scoreKeeper.addNameToUser(pointForUser, getNameByID(pointForUser))
        scoreKeeper.addUserPoint(pointForUser)

        slackClient.say(POINT_ANNOUNCEMENT_CHANNEL,
            "Point for " + getNameByID(pointForUser) + ((" on question " + qID + "!") if qID != "" else "!") \
            + (
                "\nThough they are the one who submitted it :wha:..." if pointForUser == questionKeeper.getSubmitterByQID(
                    qID) else ""))

        slackClient.say(slackClient.getDirectChannel(pointForUser), "You got question " + qID + " right!")

        return True
    return False


if __name__ == "__main__":

    slackClient = WellBehavedSlackClient(SLACK_BOT_TOKEN)

    if slackClient.rtm_connect(with_team_state=False):

        questionKeeper = QuestionKeeper()
        scoreKeeper = ScoreKeeper(slackClient)
        commandKeeper = CommandKeeper()
        pollKeeper = PollKeeper()
        messageReactionMonitor = MessageReactionMonitor(monitoredMessageCallback)

        print("QOTD Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        bot_id = slackClient.api_call("auth.test")["user_id"]
        while True:
            # The client can reject our rtm_read call for many reasons
            # So when that happens, we wait 3 seconds and try to reconnect
            # If there is no internet connection, this will continue to loop until there is
            try:
                event = slackClient.parseBotCommands(slackClient.rtm_read())
            except BaseException as e:
                log("Connection Error. Retrying in 3 seconds...")
                log("Exception details: " + str(e))
                time.sleep(3)
                try:
                    slackClient.rtm_connect(with_team_state=False)
                except BaseException as e:
                    log("Couldn't reconnect :(")
                    log("Exception details: " + str(e))
                    continue
                continue
            if event:
                commandKeeper.handle_event(event)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
