import QOTDBot as qb
from typing import List

class FakeSlackClient:
    def say(self, channel: str, response: str):
        print(response)

    def react(self, channel: str, timestamp: str, emoji: str):
        print(":" + emoji + ":")

    def devLog(self, response: str):
        print(response)

    def getDirectChannel(self, userID: str):
        return qb.DEPLOY_CHANNEL

    def getNameByID(self, userID: str):
        return "Dana Foley"

    def parseBotCommands(self, events: List[dict]):
        for event in events:
            if event["type"] == "member_joined_channel" and event["channel"] == qb.QOTD_CHANNEL:
                self.say(qb.QOTD_CHANNEL, "Welcome " + fakeGetReferenceByID(event["user"]) + "! " + qb.WELCOME_MESSAGE)


def fakeLog(response: str):
    pass

def fakeGetReferenceByID(userID: str):
    return "@dana.foley"

def fakeGetIDFromReference(userIDReference: str):
    return qb.DEVELOPER_ID


if __name__ == "__main__":
    #Overwrite production-based functions
    qb.log = fakeLog
    qb.getReferenceByID = fakeGetReferenceByID
    qb.getIDFromReference = fakeGetIDFromReference

    qb.slackClient = FakeSlackClient()

    qb.questionKeeper = qb.QuestionKeeper()
    qb.scoreKeeper = qb.ScoreKeeper(qb.slackClient)
    qb.commandKeeper = qb.CommandKeeper()
    qb.pollKeeper = qb.PollKeeper()

    #Remove command restrictions
    for c in qb.commandKeeper.commandsList:
        c.publicOnly = False
        c.privateOnly = False

    print("QOTD Bot pretending to be connected and running!")

    inputStr = ""
    qb.slackClient.parseBotCommands([{
        "type": "member_joined_channel",
        "user": "W06GH7XHN",
        "channel": qb.QOTD_CHANNEL,
        "channel_type": "G",
        "team": "T8MPF7EHL"
    }])
    while inputStr != "exit":
        inputStr = input("> ")
        event = {"user" : qb.DEVELOPER_ID, "channel" : qb.DEVELOPER_CHANNEL, "text" : inputStr}

        qb.commandKeeper.handle_event(event)


