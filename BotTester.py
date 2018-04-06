import QOTDBot as qb

def testSay(channel, response):
    print(response)

def testReact(channel, timestamp, emoji):
    print(":" + emoji + ":")

def testLog(response):
    pass

def testGetNameByID(userID):
    return "Dana Foley"

def testGetReferenceByID(userID):
    return "@dana.foley"

def testGetIDFromReference(userIDReference):
    return qb.DEVELOPER_ID

def testGetDirectChannel(userID):
    return qb.DEBUG_CHANNEL

#overwrite slack-based functions
qb.say = testSay
qb.react = testReact
qb.log = testLog
qb.getNameByID = testGetNameByID
qb.getReferenceByID = testGetReferenceByID
qb.getIDFromReference = testGetIDFromReference
qb.getDirectChannel = testGetDirectChannel

if __name__ == "__main__":
    qb.questionKeeper = qb.QuestionKeeper()
    qb.scoreKeeper = qb.ScoreKeeper()
    qb.commandKeeper = qb.CommandKeeper()
    qb.pollKeeper = qb.PollKeeper()

    #remove command restrictions
    for c in qb.commandKeeper.commandsList:
        c.publicOnly = False
        c.privateOnly = False

    print("QOTD Bot pretending to be connected and running!")

    inputStr = ""
    while inputStr != "exit":
        inputStr = input("> ")
        event = {"user" : qb.DEVELOPER_ID, "channel" : "D9C0FSD0R", "text" : inputStr}

        qb.commandKeeper.handle_event(event)


