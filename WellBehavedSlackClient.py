import time
import json
import os
import re
from slackclient import SlackClient
from typing import List, Optional, Callable

# instantiate Slack client
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
SLACK_TOKEN = os.environ.get('SLACK_TOKEN')

# QOTD Bot's user ID in Slack: value is assigned after the bot starts up
bot_id = "UNKNOWN"

# constants
RTM_READ_DELAY = 1  # 1 second delay between reading from RTM
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"  # For parsing mentions of @QOTD_Bot at the beginning of a message

QOTD_CHANNEL = "C61L4NENS"  # Where new info about questions and polls gets announced
POINT_ANNOUNCEMENT_CHANNEL = "CA7DKN1DM"  # Where points get announced

DEVELOPER_ID = "U88LK3JN9"  # Dana
DEVELOPER_CHANNEL = "D9C0FSD0R"  # Direct message channel with Dana

DEPLOY_CHANNEL = QOTD_CHANNEL

LOG_FILE = "log.txt"
FILE_LOGGING = False

USER_LIST_FILE = "userList.json"

WELCOME_MESSAGE = "I'm QOTD Bot, and I help with the the question of the day channel. I keep track of user-submitted " \
                  "questions, check answers, and keep score. You can talk to me by starting a private chat with " \
                  "@QOTDBot or putting \"@QOTDBot\" at the beginning of your message in this channel to refer to me. " \
                  "For example, say \"@QOTDBot help\" to see a list of commands I know. Feel free to speak up if you " \
                  "have any questions! "


class WellBehavedSlackClient(SlackClient):
    """Slack client with rate limit"""

    def __init__(self, token, proxies=None, rate_limit=1.0):
        super().__init__(token, proxies)
        self.rate_limit = rate_limit
        self.last_invoked = time.time() - rate_limit

    def api_call(self, method: str, timeout=None, **kwargs):
        while True:
            now = time.time()
            if (now - self.last_invoked) >= self.rate_limit:
                try:
                    result = super().api_call(method, timeout=timeout, **kwargs)
                except BaseException as e:
                    print("Connection Error. Retrying in 3 seconds...")
                    print("Exception details: " + str(e))
                    time.sleep(3)
                    continue
                self.last_invoked = time.time()
                return result
            else:
                time.sleep(self.rate_limit - (now - self.last_invoked))

    # Use this to post a message to a channel
    def say(self, channel: str, response: str):
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
    def react(self, channel: str, timestamp: str, emoji: str):
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
    def dev_log(self, response):
        global DEVELOPER_CHANNEL
        if DEVELOPER_CHANNEL is None or DEVELOPER_CHANNEL == "":
            DEVELOPER_CHANNEL = self.get_direct_channel(DEVELOPER_ID)

        self.say(DEVELOPER_CHANNEL, response)

    # If we want to send a message to a user,
    #   and the command in question wasn't sent in that user's private channel
    #   we can use an API call to open a conversation / retrieve a channel ID.
    # In the future we should cache this info to speed up response time
    def get_direct_channel(self, user_id: str) -> str:
        dm_channel = self.api_call(
            "conversations.open",
            users=user_id
        )
        return dm_channel["channel"]["id"]

    def get_name_by_id(self, user_id: str) -> str:
        # All Slack user IDs start with "U", by convention
        # So this is an easy check for invalid names
        if not user_id.startswith('U'):
            return user_id

        # Our top priority is to get the name from the score sheet,
        # since we can change that to a person's preference if they don't want to use their display name
        # nameFromScoreSheet = scoreKeeper.getUserNameInScoreSheet(user_id)
        # if nameFromScoreSheet:
        #     userName = nameFromScoreSheet
        #     return userName

        # Next highest priority is to use the bulk list of all users we can manually pull from Slack
        with open(USER_LIST_FILE) as usersFile:
            users_dict = json.load(usersFile)
        if user_id in users_dict:
            user_name = users_dict[user_id]
            return user_name

        # Last ditch effort is to do an api call, which we really want to avoid
        attempted_name_json = self.api_call(
            "users.info",
            token=SLACK_BOT_TOKEN,
            user=user_id
        )
        if attempted_name_json["ok"]:
            if attempted_name_json["user"]["profile"]["display_name"] != "":
                user_name = attempted_name_json["user"]["profile"]["display_name"]
            else:
                user_name = attempted_name_json["user"]["profile"]["real_name"]
        else:
            user_name = user_id

        return user_name

    def parse_bot_commands(self, slack_events: List[dict]) -> Optional[dict]:
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
            if event["type"] == "member_joined_channel" and event["channel"] == QOTD_CHANNEL:
                self.say(QOTD_CHANNEL, "Welcome " + get_reference_by_id(event["user"]) + "! " + WELCOME_MESSAGE)
            if event["type"] == "message" and "subtype" not in event:
                processed_event = self.parse_direct_mention(event)
                if processed_event:
                    log(self.get_name_by_id(event["user"]) + " says: " + event["text"] + "\n")
                    return processed_event
        return None

    @staticmethod
    def parse_direct_mention(event: dict) -> Optional[dict]:
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
        elif is_event_private(event):
            # return (bot_id, message_text)
            return event
        else:
            return None

    @staticmethod
    def set_bot_id(new_bot_id: str):
        global bot_id
        bot_id = new_bot_id


# Just for keeping/printing a history of what was said.
# We might keep file logging off if the frequent read/write causes lag or disk wear,
#   but no reason not to print
def log(response: str):
    if FILE_LOGGING:
        file = open(LOG_FILE, "a", newline='', encoding='utf8')
        file.write(response)
        file.close()
    print(response)


# References to users appear to begin with "@" in Slack, followed by a person's name
# But behind the scenes, they're user IDs wrapped up in "<>" characters, e.g. "<@U1234ABCD>"
# So if we want to reference a user when posting a message, we take their ID, and wrap it.
def get_reference_by_id(user_id: str) -> str:
    return "<@" + user_id + ">"


# Similarly, if we want to get an ID from a reference, we just strip the wrapping
def get_id_from_reference(user_id_reference: str) -> str:
    for char in "<>@":
        user_id_reference = user_id_reference.replace(char, "")
    user_id = user_id_reference.strip()
    return user_id


def check_public(message_event: dict) -> str:
    if not is_event_private(message_event):
        return "You can't use this command in a public channel. Message me directly instead"
    else:
        return ""


def check_private(message_event: dict) -> str:
    if is_event_private(message_event):
        return "You can't use this command in a private channel. Use the public channel instead"
    else:
        return ""


def is_channel_private(channel: str) -> bool:
    """Checks if public slack channel"""
    return channel.startswith('D')


def is_event_private(message_event: dict) -> bool:
    """Checks if private slack channel"""
    return message_event['channel'].startswith('D')
