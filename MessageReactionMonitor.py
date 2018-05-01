import time
import json
from tempfile import NamedTemporaryFile
import shutil

MESSAGES_FILE_NAME = "monitoredMessages.json"


class MonitoredMessage:
    def __init__(self, channel, userID, timestamp, callbackKey, data):
        self.channel = channel
        self.userID = userID
        self.timestamp = timestamp
        self.callbackKey = callbackKey
        self.data = data
        self.initTime = time.time()

class MessageReactionMonitor:
    def __init__(self, slackClient, callbackFunc):
        self.slackClient = slackClient
        #The callback function must be passed in from QOTDBot since it modifies other modules
        self.callbackFunc = callbackFunc
        self.messagesList = []
        self.loadMessagesFromFile()

    def loadMessagesFromFile(self):
        try:
            file = open(MESSAGES_FILE_NAME)
        except:
            # If not exists, create the file
            messagesJson = {"monitoredMessages" : []}
            file = open(MESSAGES_FILE_NAME,"w+")
            json.dump(messagesJson, file, indent = 4)
        file.close()

        with open(MESSAGES_FILE_NAME) as qFile:
            d = json.load(qFile)
            for mJson in d["monitoredMessages"]:
                m = MonitoredMessage(mJson["channel"], mJson["userID"], mJson["timestamp"], mJson["data"], mJson["callbackKey"])
                m.initTime = mJson["initTime"]
                self.messagesList.append(m)

    def writeMessagesToFile(self):
        messagesJson = {"questions" : []}

        self.expireOldMessages()

        for m in self.messagesList:
            messagesJson["questions"].append(vars(m))

        tempfile = NamedTemporaryFile(delete=False)
        with open(MESSAGES_FILE_NAME, 'w') as tempfile:
            json.dump(messagesJson, tempfile, indent = 4)

        shutil.move(tempfile.name, MESSAGES_FILE_NAME)

    def expireOldMessages(self):
        now = time.time()
        maxAge = 60 * 60 * 24 * 5  # 5 days
        self.messagesList = [m for m in self.messagesList if (now - m.initTime) < maxAge]

    def addMonitoredMessage(self, channel, userID, timestamp, callbackKey, data):
        self.messagesList.append(MonitoredMessage(channel, userID, timestamp, callbackKey, data))
        self.writeMessagesToFile()

    def getMonitoredMessage(self, channel, timestamp):
        for m in self.messagesList:
            if m.timestamp == timestamp and m.channel == channel:
                return m
        return None

    def reactionAdded(self, channel, timestamp, userWhoReacted, emoji):
        self.expireOldMessages()
        monitoredMessage = self.getMonitoredMessage(channel, timestamp)
        if monitoredMessage is None:
            return
        #Run the callback function. If it returns true, we can remove it
        if self.callbackFunc(userWhoReacted, emoji, monitoredMessage.callbackKey, monitoredMessage.data):
            self.messagesList.remove(monitoredMessage)


