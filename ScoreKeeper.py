import csv
import shutil
from datetime import datetime, timedelta
from typing import Optional

SCORES_FILE_NAME = "scores.csv"


def to_int(s):
    s = str(s).strip()
    return int(s) if s else 0


class ScoreKeeper:
    def __init__(self, slack_client):
        self.slackClient = slack_client
        self.data = []
        self.today_row_num = -1  # error value
        self.totals_row_num = 2  # manually chosen
        self.user_id_row_num = 0  # manually chosen
        self.user_name_row_num = 1  # manually chosen

        self.get_data_from_file()
        self.catch_up_date_rows()

    def get_today_scores(self) -> str:
        scores_list = []
        today_scores = self.data[self.today_row_num]
        for column, score in enumerate(today_scores):
            if column == 0:
                continue
            if score != "":
                scores_list.append(self.data[self.user_name_row_num][column] + " - " + str(score))
        if len(scores_list) > 0:
            scores_list.sort(key=lambda s: s.lower())
            return "*Today's scores*:\n" + "\n".join(scores_list) + "\n\n"
        else:
            return "No new scores from today.\n"

    def get_today_scores_ranked(self) -> str:
        scores_list = []
        today_scores = self.data[self.today_row_num]
        for column, score in enumerate(today_scores):
            if column == 0:
                continue
            if score != "":
                scores_list.append((int(score), self.data[self.user_name_row_num][column]))
        if len(scores_list) > 0:
            scores_list.sort(reverse=True)
            for idx, tupl in enumerate(scores_list):
                user = tupl[1]
                score = tupl[0]

                scores_list[idx] = str(idx + 1) + ": " + user + " - " + str(score)

            return "*Today's scores*:\n" + "\n".join(scores_list) + "\n\n"
        else:
            return "No new scores from today.\n"

    def get_total_scores(self) -> str:
        scores_list = []
        total_scores = self.data[self.totals_row_num]
        for column, score in enumerate(total_scores):
            if column == 0:
                continue
            if score != "" and str(score) != "0":
                scores_list.append(self.data[self.user_name_row_num][column] + " - " + str(score))

        scores_list.sort(key=lambda s: s.lower())
        return "*Total scores from this month*:\n" + "\n".join(scores_list) + "\n"

    def get_total_scores_ranked(self) -> str:
        scores_list = []
        total_scores = self.data[self.totals_row_num]
        for column, score in enumerate(total_scores):
            if column == 0:
                continue
            if score != "" and str(score) != "0":
                scores_list.append((int(score), self.data[self.user_name_row_num][column]))

        scores_list.sort(reverse=True)
        for idx, tupl in enumerate(scores_list):
            user = tupl[1]
            score = tupl[0]

            scores_list[idx] = str(idx + 1) + ": " + user + " - " + str(score)
        return "*Total scores from this month*:\n" + "\n".join(scores_list) + "\n"

    def get_user_scores(self, user_id: str) -> str:
        output = ""
        today_score = ""
        total_score = ""
        column = None

        if self.user_exists(user_id):
            column = self.get_user_column_num(user_id)
            today_score = str(self.data[self.today_row_num][column])
            total_score = str(self.data[self.totals_row_num][column])

        if today_score != "":
            output += self.data[self.user_name_row_num][column] + "'s points from today: " + today_score + '\n'
        if total_score != "":
            output += self.data[self.user_name_row_num][column] + "'s total points: " + total_score

        if output == "":
            output = "I couldn't find any score data for that user"

        return output

    def update_file_with_data(self):
        with open(SCORES_FILE_NAME, 'w', newline='') as tempfile:
            writer = csv.writer(tempfile)

            for row in self.data:
                writer.writerow(row)

        shutil.move(tempfile.name, SCORES_FILE_NAME)

    def catch_up_date_rows(self):

        row_length = len(self.data[0])

        today = datetime.today().date()
        last_date = datetime.strptime(self.data[-1][0], "%m/%d/%Y").date()

        if today.month > last_date.month:
            self.announce_montly_winners(last_date.strftime("%B"))

        if last_date < today:
            needs_catch_up = True
        else:
            needs_catch_up = False

        while last_date < today:
            last_date += timedelta(days=1)
            self.data.append([last_date.strftime("%m/%d/%Y")] + ([""] * row_length))

        if needs_catch_up:
            self.calculate_monthly_totals()
            self.update_file_with_data()

            self.today_row_num = len(self.data) - 1

    def user_exists(self, user_id: str) -> bool:
        return user_id in self.data[self.user_id_row_num]

    def get_user_column_num(self, user_id: str) -> int:
        if user_id in self.data[self.user_id_row_num]:
            return self.data[self.user_id_row_num].index(user_id)
        else:
            return -1

    def get_user_name_in_score_sheet(self, user_id: str) -> Optional[str]:
        column = self.get_user_column_num(user_id)

        if column != -1:
            return self.data[self.user_name_row_num][column]
        else:
            return None

    def set_user_name_in_score_sheet(self, user_id: str, new_name: str):
        column = self.get_user_column_num(user_id)

        if column != -1:
            self.data[self.user_name_row_num][column] = new_name
            return True
        else:
            return False

    def add_new_user(self, user_id: str):
        for idx, row in enumerate(self.data):
            self.data[idx].append("")
        self.data[self.totals_row_num][-1] = 0
        self.data[self.user_id_row_num][-1] = user_id

    def add_name_to_user(self, user_id: str, user_name: str):
        column_num = self.get_user_column_num(user_id)
        self.data[self.user_name_row_num][column_num] = user_name

    def add_user_point(self, user_id: str):
        self.add_user_points(user_id, 1)

    def add_user_points(self, user_id: str, num_points: int):

        self.catch_up_date_rows()

        column_num = self.get_user_column_num(user_id)
        if column_num == -1:
            self.add_new_user(user_id)
            column_num = self.get_user_column_num(user_id)
        if self.data[self.today_row_num][column_num] == "":
            self.data[self.today_row_num][column_num] = 0

        self.data[self.today_row_num][column_num] = int(self.data[self.today_row_num][column_num]) + num_points
        self.data[self.totals_row_num][column_num] = int(self.data[self.totals_row_num][column_num]) + num_points
        self.update_file_with_data()

    def get_data_from_file(self):
        file = open(SCORES_FILE_NAME, "r")
        self.data = list(csv.reader(file))
        file.close()

    @staticmethod
    def back_up_data():
        file = open(SCORES_FILE_NAME, "r")
        scores = file.read()
        file.close()
        return scores

    def announce_montly_winners(self, month_name: str):
        scores_list = []
        total_scores = self.data[self.totals_row_num]
        for column, score in enumerate(total_scores):
            if column == 0:
                continue
            if score != "" and str(score) != "0":
                scores_list.append((int(score), self.data[self.user_name_row_num][column]))

        scores_list.sort(reverse=True)
        scores_list = scores_list[:min(3, len(scores_list))]
        for idx, tupl in enumerate(scores_list):
            user = tupl[1]
            score = tupl[0]

            scores_list[idx] = str(idx + 1) + ": " + user + " - " + str(score)

        self.slackClient.say("DEPLOY_CHANNEL", "Winners from " + month_name + "!\n" + "\n".join(scores_list) + "\n")

    def calculate_monthly_totals(self):
        today_month = int(self.data[self.today_row_num][0].split("/")[0])

        temp_row = self.today_row_num
        temp_month = today_month

        totals = [0] * (len(self.data[temp_row]) - 1)

        while temp_month == today_month:
            totals = [sum(x) for x in zip(totals, [to_int(s) for s in self.data[temp_row][1:]])]
            temp_row -= 1
            temp_month = int(self.data[temp_row][0].split("/")[0])

        self.data[self.totals_row_num][1:] = totals
        self.update_file_with_data()
