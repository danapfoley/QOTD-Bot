from time import time, sleep
import json
import os
import re
from slackclient import SlackClient

# instantiate Slack client
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
SLACK_TOKEN = os.environ.get('SLACK_TOKEN')

# starterbot's user ID in Slack: value is assigned after the bot starts up
bot_id = "UNKNOWN"

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
MENTION_REGEX = "^<@(|[WU].+?)>(.*)" #For parsing mentions of @QOTD_Bot at the beginning of a message

QOTD_CHANNEL = "C61L4NENS" #Where new info about questions and polls gets announced
POINT_ANNOUNCEMENT_CHANNEL = "CA7DKN1DM" #Where points get announced

DEVELOPER_ID = "U88LK3JN9" #Dana
DEVELOPER_CHANNEL = "D9C0FSD0R" #Direct message channel with Dana

DEPLOY_CHANNEL = QOTD_CHANNEL

LOG_FILE = "log.txt"
FILE_LOGGING = False

USER_LIST_FILE = "userList.json"

class WellBehavedSlackClient(SlackClient):
    '''Slack client with rate limit'''

    def __init__(self, token, proxies=None, ratelimit=1.0):
        super().__init__(token, proxies)
        self.ratelimit = ratelimit
        self.last_invoked = time() - ratelimit

    def api_call(self, method, timeout=None, **kwargs):
        while True:
            now = time()
            if (now - self.last_invoked) >= self.ratelimit:
                try:
                    result = super().api_call(method, timeout=timeout, **kwargs)
                except BaseException as e:
                    print("Connection Error. Retrying in 3 seconds...")
                    print("Exception details: " + str(e))
                    sleep(3)
                    continue
                self.last_invoked = time()
                return result
            else:
                sleep(self.ratelimit - (now - self.last_invoked))

    # Use this to post a message to a channel
    def say(self, channel, response):
        if channel == "" or channel == "DEPLOY_CHANNEL":
            channel = DEPLOY_CHANNEL
        try:
            self.api_call(
                "chat.postMessage",
                channel=channel,
                text=response,
                icon_emoji=':robot_face:'
            )
            log("QOTD Bot says: " + (response if response else "[BLANK MESSAGE]") + "\n")
        except ValueError:
            log("QOTD Bot failed to say: " + (response if response else "[BLANK MESSAGE]") + "\n")

    # Use this to add an emoji reaction to a message.
    # The timestamp can easily come from the command message, if that's what you're reacting to.
    # Reacting to older messages requires more effort to hang on to the timestamp, because we can't retrieve it later.
    def react(self, channel, timestamp, emoji):
        try:
            self.api_call(
                "reactions.add",
                channel=channel,
                timestamp=timestamp,
                name=emoji
            )
            log("QOTD Bot reacts with: " + (emoji if emoji else "[NO EMOJI]") + "\n")
        except ValueError:
            log("QOTD Bot failed to react with: " + (emoji if emoji else "[NO EMOJI]") + "\n")

    # Send an action log to the chosen dev.
    # This is currently used to send exception details + stacktrace directly to the dev when an error is caught
    #   for ~efficient development~
    def devLog(self, response):
        global DEVELOPER_CHANNEL
        if DEVELOPER_CHANNEL is None or DEVELOPER_CHANNEL == "":
            DEVELOPER_CHANNEL = self.getDirectChannel(DEVELOPER_ID)

        self.say(DEVELOPER_CHANNEL, response)

    # If we want to send a message to a user,
    #   and the command in question wasn't sent in that user's private channel
    #   we can use an API call to open a conversation / retrieve a channel ID.
    # In the future we should cache this info to speed up response time
    def getDirectChannel(self, userID):
        dmChannel = self.api_call(
            "conversations.open",
            users=userID
        )
        return dmChannel["channel"]["id"]

    def getNameByID(self, userID):
        # All Slack user IDs start with "U", by convention
        # So this is an easy check for invalid names
        if not userID.startswith('U'):
            return userID

        # Our top priority is to get the name from the score sheet,
        # since we can change that to a person's preference if they don't want to use their display name
        # nameFromScoreSheet = scoreKeeper.getUserNameInScoreSheet(userID)
        # if nameFromScoreSheet:
        #     userName = nameFromScoreSheet
        #     return userName

        # Next highest priority is to use the bulk list of all users we can manually pull from Slack
        with open(USER_LIST_FILE) as usersFile:
            usersDict = json.load(usersFile)
        if userID in usersDict:
            userName = usersDict[userID]
            return userName

        # Last ditch effort is to do an api call, which we really want to avoid
        attemptedNameJson = self.api_call(
            "users.info",
            token=SLACK_BOT_TOKEN,
            user=userID
        )
        if attemptedNameJson["ok"]:
            if attemptedNameJson["user"]["profile"]["display_name"] != "":
                userName = attemptedNameJson["user"]["profile"]["display_name"]
            else:
                userName = attemptedNameJson["user"]["profile"]["real_name"]
        else:
            userName = userID

        return userName

    def parseBotCommands(self, slack_events):
        """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
        """
        for event in slack_events:
            if event["type"] == "goodbye":
                print("Got 'goodbye' message. Reconnecting now")
                self.rtm_connect(with_team_state=False)
            if event["type"] == "error":
                print("Network error. Retrying in 5 seconds...\n")
                time.sleep(5)
                return None
            if event["type"] == "message" and not "subtype" in event:
                processedEvent = self.parseDirectMention(event)
                if processedEvent:
                    log(self.getNameByID(event["user"]) + " says: " + event["text"] + "\n")
                    return processedEvent
        return None

    def parseDirectMention(self, event):
        message_text = event["text"]
        """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
        """
        matches = re.search(MENTION_REGEX, message_text)
        # the first group contains the username, the second group contains the remaining message
        # If direct mention...
        if matches and matches.group(1) == bot_id:
            event["text"] = matches.group(2).strip()
            # return (matches.group(1), matches.group(2).strip())
            return event
        # If private message (no mention necessary)
        elif isEventPrivate(event):
            # return (bot_id, message_text)
            return event
        else:
            return None

    def setBotID(self, newBotID):
        global bot_id
        bot_id = newBotID


# Just for keeping/printing a history of what was said.
# We might keep file logging off if the frequent read/write causes lag or disk wear,
#   but no reason not to print
def log(response):
    if FILE_LOGGING:
        file = open(LOG_FILE, "a", newline='', encoding='utf8')
        file.write(response)
        file.close()
    print(response)

# References to users appear to begin with "@" in Slack, followed by a person's name
# But behind the scenes, they're user IDs wrapped up in "<>" characters, e.g. "<@U1234ABCD>"
# So if we want to reference a user when posting a message, we take their ID, and wrap it.
def getReferenceByID(userID):
    return "<@" + userID + ">"

# Similarly, if we want to get an ID from a reference, we just strip the wrapping
def getIDFromReference(userIDReference):
    for char in "<>@":
        userIDReference = userIDReference.replace(char, "")
    userID = userIDReference.strip()
    return userID

def checkPublic(messageEvent):
    if not isEventPrivate(messageEvent):
        return "You can't use this command in a public channel. Message me directly instead"
    else:
        return ""

def checkPrivate(messageEvent):
    if isEventPrivate(messageEvent):
        return "You can't use this command in a private channel. Use the public channel instead"
    else:
        return ""

def isChannelPrivate(channel):
    """Checks if public slack channel"""
    return channel.startswith('D')

def isEventPrivate(messageEvent):
    """Checks if private slack channel"""
    return messageEvent['channel'].startswith('D')




