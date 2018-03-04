import csv
from tempfile import NamedTemporaryFile
import shutil
from datetime import date, datetime, timedelta

SCORES_FILE_NAME = "scores.csv"

def to_int(s):
    s = s.strip()
    return int(s) if s else 0

class ScoreKeeper:
    def __init__(self):
        self.data = []
        self.todayRowNum = -1 #error value
        self.totalsRowNum = 2 #manually set
        self.userIDRowNum = 0 #manually set
        self.userNameRowNum = 1 #manually set

        self.catchUpDateRows()
        self.getDataFromFile()
        self.calculateMonthlyTotals()

    def getTodayScores(self):
        scoresList = []
        todayScores = self.data[self.todayRowNum]
        for column, score in enumerate(todayScores):
            if column == 0:
                continue
            if score != "":
                 scoresList.append(self.data[self.userNameRowNum][column] + " - " + str(score))
        if len(scoresList) > 0:
            scoresList.sort(key=lambda s: s.lower())
            return "*Today's scores*:\n" + "\n".join(scoresList) + "\n\n"
        else:
            return "No new scores from today.\n"

    def getTodayScoresRanked(self):
        scoresList = []
        todayScores = self.data[self.todayRowNum]
        for column, score in enumerate(todayScores):
            if column == 0:
                continue
            if score != "":
                 scoresList.append((int(score), self.data[self.userNameRowNum][column]))
        if len(scoresList) > 0:
            scoresList.sort(reverse = True)
            for idx, tuple in enumerate(scoresList):
                user = tuple[1]
                score = tuple[0]

                scoresList[idx] = str(idx + 1) + ": " + user + " - " + str(score)

            return "*Today's scores*:\n" + "\n".join(scoresList) + "\n\n"
        else:
            return "No new scores from today.\n"

    def getTotalScores(self):
        scoresList = []
        totalScores = self.data[self.totalsRowNum]
        for column, score in enumerate(totalScores):
            if column == 0:
                continue
            if score != "" and str(score) !="0":
                 scoresList.append(self.data[self.userNameRowNum][column] + " - " + str(score))
        
        scoresList.sort(key=lambda s: s.lower())
        return "*Total scores from this month*:\n" + "\n".join(scoresList) + "\n"

    def getTotalScoresRanked(self):
        scoresList = []
        totalScores = self.data[self.totalsRowNum]
        for column, score in enumerate(totalScores):
            if column == 0:
                continue
            if score != "" and str(score) != "0":
                scoresList.append((int(score), self.data[self.userNameRowNum][column]))
        
        scoresList.sort(reverse = True)
        for idx, tuple in enumerate(scoresList):
            user = tuple[1]
            score = tuple[0]

            scoresList[idx] = str(idx + 1) + ": " + user + " - " + str(score)
        return "*Total scores from this month*:\n" + "\n".join(scoresList) + "\n"

    def getUserScores(self, userID):
        output = ""
        todayScore = ""
        totalScore = ""

        if self.userExists(userID):
            column = self.getUserColumnNum(userID)
            todayScore = str(self.data[self.todayRowNum][column])
            totalScore = str(self.data[self.totalsRowNum][column])

        if todayScore != "":
            output += self.data[self.userNameRowNum][column] + "'s points from today: " + todayScore + '\n'
        if totalScore != "":
            output += self.data[self.userNameRowNum][column] + "'s total points: " + totalScore
            
        if output == "":
            output = "I couldn't find any score data for that user"

        return output
        
    def updateFileWithData(self):
        tempfile = NamedTemporaryFile(delete=False)
        with open(SCORES_FILE_NAME, 'w', newline='') as tempfile:
            writer = csv.writer(tempfile)

            for row in self.data:
                writer.writerow(row)

        shutil.move(tempfile.name, SCORES_FILE_NAME)

    def catchUpDateRows(self):
        file = open(SCORES_FILE_NAME,"r")
        reader = list(csv.reader(file))
        file.close()
        
        numRows = len(reader)
        rowLength = len(reader[0])

        today = datetime.today().date()
        lastDate = datetime.strptime(reader[-1][0], "%m/%d/%Y").date()
        newData=[]
        if lastDate < today:
            needsCatchUp = True
        else:
            needsCatchUp = False

        while lastDate < today:
            lastDate += timedelta(days=1)
            numRows += 1
            newData.append([lastDate.strftime("%m/%d/%Y")] + ([""] * rowLength))

        if needsCatchUp:
            file = open(SCORES_FILE_NAME, "a", newline='')
            writer = csv.writer(file)
            writer.writerows(newData)
            file.close()

        self.todayRowNum = numRows - 1
        
    def userExists(self, userID):
        return userID in self.data[self.userIDRowNum]

    def getUserColumnNum(self, userID):
        if userID in self.data[self.userIDRowNum]:
            return self.data[self.userIDRowNum].index(userID)
        else:
            return -1

    def getUserNameInScoreSheet(self, userID):
        column = self.getUserColumnNum(userID)

        if column != -1:
            return self.data[self.userNameRowNum][column]
        else:
            return None

    def addNewUser(self, userID):
        for idx, row in enumerate(self.data):
            self.data[idx].append("")
        self.data[self.totalsRowNum][-1] = 0
        self.data[self.userIDRowNum][-1] = userID

    def addNameToUser(self, userID, userName):
        columnNum = self.getUserColumnNum(userID)
        self.data[self.userNameRowNum][columnNum] = userName

    def addUserPoint(self, userID):
        self.addUserPoints(userID, 1)

    def addUserPoints(self, userID, numPoints):
        if not self.userExists(userID):
            self.addNewUser(userID)
            self.addNameToUser(userID, getNameByID(userID))

        columnNum = self.getUserColumnNum(userID)
        if columnNum == -1:
            self.addNewUser(userID)
            columnNum = self.getUserColumnNum(userID)
        if self.data[self.todayRowNum][columnNum] == "":
            self.data[self.todayRowNum][columnNum] = 0

        self.data[self.todayRowNum][columnNum]  = int(self.data[self.todayRowNum][columnNum]) + numPoints
        self.data[self.totalsRowNum][columnNum] = int(self.data[self.totalsRowNum][columnNum]) + numPoints
        self.updateFileWithData()

    def getDataFromFile(self):
        file = open(SCORES_FILE_NAME,"r")
        self.data = list(csv.reader(file))
        file.close()

    def calculateMonthlyTotals(self):
        todayMonth = int(self.data[self.todayRowNum][0].split("/")[0])

        tempRow = self.todayRowNum
        tempMonth = todayMonth

        totals = [0] * (len(self.data[tempRow]) -1)

        while tempMonth == todayMonth:
            totals = [sum(x) for x in zip(totals, [to_int(s) for s in self.data[tempRow][1:]])]
            tempRow -= 1
            tempMonth = int(self.data[tempRow][0].split("/")[0])

        self.data[self.totalsRowNum][1:] = totals
        self.updateFileWithData()


