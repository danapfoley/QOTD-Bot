import QOTDBot as qb

class FakeSlackClient:
    def say(self, channel, response):
        print(response)

    def react(self, channel, timestamp, emoji):
        print(":" + emoji + ":")

    def devLog(self, response):
        print(response)

    def getDirectChannel(self, userID):
        return qb.DEPLOY_CHANNEL

    def getNameByID(self, userID):
        return "Dana Foley"


def fakeLog(response):
    pass

def fakeGetReferenceByID(userID):
    return "@dana.foley"

def fakeGetIDFromReference(userIDReference):
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
    while inputStr != "exit":
        inputStr = input("> ")
        event = {"user" : qb.DEVELOPER_ID, "channel" : qb.DEVELOPER_CHANNEL, "text" : inputStr}

        qb.commandKeeper.handle_event(event)


