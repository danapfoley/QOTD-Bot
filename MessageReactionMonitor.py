import json
from tempfile import NamedTemporaryFile
import shutil

MESSAGES_FILE_NAME = "monitoredMessages.json"

class MonitoredMessage:
    def __init__(self, channel, userID, timestamp, data, callback, removeAfterCallback = False):
        self.channel = channel
        self.userID = userID
        self.timestamp = timestamp
        self.data = data
        self.callback = callback
        self.removeAfterCallback = removeAfterCallback

    def reactionAdded(self, userWhoReacted, emoji):
        self.callback(userWhoReacted, emoji, self.data)

class MessageReactionMonitor:
    def __init__(self):
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
                m = MonitoredMessage(mJson["channel"], mJson["userID"], mJson["timestamp"], mJson["data"], mJson["callback"], mJson["removeAfterCallback"])
                self.messagesList.append(m)

    def writeMessagesToFile(self):
        messagesJson = {"questions" : []}

        for m in self.messagesList:
            messagesJson["questions"].append(vars(m))

        tempfile = NamedTemporaryFile(delete=False)
        with open(MESSAGES_FILE_NAME, 'w') as tempfile:
            json.dump(messagesJson, tempfile, indent = 4)

        shutil.move(tempfile.name, MESSAGES_FILE_NAME)

    def addMonitoredMessage(self, channel, userID, timestamp, data, callback):
        self.messagesList.append(MonitoredMessage(channel, userID, timestamp, data, callback))

    def getMonitoredMessage(self, channel, timestamp):
        for m in self.messagesList:
            if m.timestamp == timestamp and m.channel == channel:
                return m
        return None

    def reactionAdded(self, channel, timestamp, userWhoReacted, emoji):
        monitoredMessage = self.getMonitoredMessage(channel, timestamp)
        if monitoredMessage is None:
            return
        monitoredMessage.reactionAdded(userWhoReacted, emoji)


