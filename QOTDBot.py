import os
import time
import re
import json, requests
from slackclient import SlackClient


# instantiate Slack client
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
print(os.environ.get('SLACK_BOT_TOKEN'))
# starterbot's user ID in Slack: value is assigned after the bot starts up
starterbot_id = None

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
HELP_COMMAND = "help"
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"

#Commands stuff
#----------------------------------

def say(channel, response):
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response
    )

def help(args):
    channel, args = args[0], args[1:]
    response = ""
    if args:
        response += "Not sure what you meant by \"" + ' '.join(args) + "\", but here's some help if you need it!\n"
    response += "(Some helpful stuff)"
    say(channel, response)

def scores(args):
    channel, args = args[0], args[1:]
    response = "Here's where I'd say what the scores are!"
    say(channel, response)
    return response

def addQuestion(args):
    channel, args = args[0], args[1:]
    response = ""
    if not args:
        response += "Usage: "
    if (not args) or args[0].lower() == "help":
        response += "`question [identifier] [question] [answer] <needs manual confirmation? (true/false, default true)>`\n"
        if not is_channel_private(channel):
            response += "But you can't use that in a public channel! Message me directly instead"
        say(channel, response)
        return response
    elif not is_channel_private(channel):
        response += "You can't use that in a public channel! Message me directly instead"
        say(channel, response)
        return response
    response = "Here's where I'd say what the scores are!"
    say(channel, response)
    return response

    

commandsDict = {
    "help" : help,
    "scores" : scores,
    "score" : scores,
    "points" : scores,
    "question" : addQuestion
}


#----------------------------------

def is_channel_private(channel):
    return channel.startswith('D')

def is_event_private(event):
    """Checks if private slack channel"""
    return event.get('channel').startswith('D')


def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event)
            if user_id == starterbot_id:
                print("received direct mention from " + user_id + ": " + message)
                return message, event["channel"]
    return None, None

def parse_direct_mention(event):
    message_text = event["text"]
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    #If direct mention...
    if matches:
        return (matches.group(1), matches.group(2).strip())
    #If private message (no mention necessary)
    elif is_event_private(event):
        return (starterbot_id, message_text)
    else:
        return (None, None)

def handle_command(command, channel):
    """
        Executes bot command if the command is known
    """
    # Default response is help text for the user
    default_response = "Not sure what you mean. Try *{}* for more info.".format(HELP_COMMAND)

    # Finds and executes the given command, filling in response
    response = None
    # This is where you start to implement more commands!
    command_id = command.split(' ', 1)[0].lower()
    command_args = [channel] + command.split(' ')[1:]
    func = commandsDict[command_id]
    func(command_args)


if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Starter Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        starterbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            command, channel = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(command, channel)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")