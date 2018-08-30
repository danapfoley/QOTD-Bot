import json
import shutil
from typing import List, Dict, Optional

POLLS_FILE_NAME = "polls.json"


class PollQuestion:
    def __init__(self, user_id, p_id, poll_question_text, options=None, responses=None):
        if responses is None:
            responses = {}
        if options is None:
            options = {}
        self.user_id: str = user_id
        self.p_id: str = p_id
        self.poll_question_text: str = poll_question_text
        self.options: Dict[str, str] = options
        self.responses: Dict[str, str] = responses
        self.published: bool = False
        self.just_published: bool = False
        self.results: Dict[str, int] = {}

    @staticmethod
    def clean_up_response(response: str):
        response = response.lower().strip()
        remove_chars = ["'", "’", "-"]

        for char in remove_chars:
            response = response.replace(char, "")

        return response

    def submit_response(self, user_id: str, input_response: str) -> bool:
        if input_response in self.options.keys():
            self.responses[user_id] = input_response
            return True
        return False

    def pretty_print(self) -> str:
        output = "(" + self.p_id + "): " + self.poll_question_text + "\n"

        for option in sorted(self.options.keys()):
            output += "    (" + option + "): " + self.options[option] + "\n"

        return output

    def calculate_results(self):
        for key in self.options.keys():
            self.results[key] = 0
        for vote in self.responses.values():
            if vote in self.results:
                self.results[vote] += 1
            else:
                self.results[vote] = 1

    def display_results(self) -> str:
        self.calculate_results()

        output = "(" + self.p_id + "): " + self.poll_question_text + "\n"

        for option in self.results:
            output += "    " + str(self.results[option]) + " - " + self.options[option] + "\n"

        output = "\n".join(sorted(output.split("\n"), reverse=True))
        return output

    def publish(self) -> bool:
        if self.published:
            return False
        else:
            self.published = True
            self.just_published = True
            return True


class PollKeeper:
    def __init__(self):
        self.poll_question_list = []
        self.load_polls_from_file()

    def load_polls_from_file(self):
        with open(POLLS_FILE_NAME) as pFile:
            d = json.load(pFile)
            for p_json in d["polls"]:
                p = PollQuestion(p_json["user_id"], p_json["pID"], p_json["pollQuestionText"], p_json["options"],
                                 p_json["responses"])
                p.published = p_json["published"]
                p.just_published = p_json["justPublished"]

                self.poll_question_list.append(p)

    def write_polls_to_file(self):
        polls_json = {"polls": []}

        for p in self.poll_question_list:
            polls_json["polls"].append(vars(p))

        with open(POLLS_FILE_NAME, 'w') as tempfile:
            json.dump(polls_json, tempfile, indent=4)

        shutil.move(tempfile.name, POLLS_FILE_NAME)

    def add_poll(self, user_id: str, p_id: str, poll_question_text: str, options=None, responses=None) -> bool:

        if options is None:
            options = {}
        if responses is None:
            responses = {}
        for p in self.poll_question_list:
            if p_id.lower() == p.p_id.lower():
                return False

        self.poll_question_list.append(PollQuestion(user_id, p_id, poll_question_text, options, responses))

        # save new data
        self.write_polls_to_file()
        return True

    def remove_poll(self, p_id: str, user_id: str) -> bool:

        for p in self.poll_question_list:
            if p_id.lower() == p.p_id.lower() and (p.user_id == user_id or user_id == "DEV"):
                self.poll_question_list.remove(p)

                # save new data
                self.write_polls_to_file()
                return True
        return False

    def get_poll_by_id(self, p_id: str) -> Optional[PollQuestion]:
        for p in self.poll_question_list:
            if p_id.lower() == p.p_id.lower():
                return p

        return None

    def get_submitter_by_pid(self, p_id):
        p = self.get_poll_by_id(p_id)
        if p:
            return p.user_id
        else:
            return None

    def submit_response(self, user_id: str, p_id: str, input_response: str) -> str:
        p = self.get_poll_by_id(p_id)
        if p and p.published:
            if p.submit_response(user_id, input_response):
                self.write_polls_to_file()
                return "ok"
            else:
                return "bad vote"

        return "not found"

    def list_polls(self) -> str:
        output = ""
        for p in self.poll_question_list:
            if p.published:
                output += p.pretty_print() + "\n"
        return output

    def list_polls_by_user(self, user_id: str) -> str:
        output = ""
        for p in self.poll_question_list:
            if p.user_id == user_id:
                output += p.pretty_print() + (" (published)" if p.published else "") + "\n"
        return output

    def expire_poll(self, p_id: str, user_id: str) -> List[PollQuestion]:
        polls_expired = []

        if p_id != "":
            p = self.get_poll_by_id(p_id)
            if p is None:
                return polls_expired
            if p.user_id == user_id:
                polls_expired.append(p)
        else:
            for p in self.poll_question_list:
                if p.user_id == user_id:
                    polls_expired.append(p)

        self.poll_question_list: List[PollQuestion] = [p for p in self.poll_question_list if p not in polls_expired]
        polls_expired = [p.pretty_print() for p in polls_expired]
        self.write_polls_to_file()

        return polls_expired

    def publish_by_id(self, p_id: str) -> str:
        p = self.get_poll_by_id(p_id)
        if p:
            if p.publish():
                self.write_polls_to_file()
                return "published"
            else:
                return "already published"
        else:
            return "notFound"

    def publish_all_by_user(self, user_id: str):
        for p in self.poll_question_list:
            if p.user_id == user_id:
                p.publish()
        self.write_polls_to_file()

    def first_time_display(self) -> str:
        output = ""
        for p in self.poll_question_list:
            if p.justPublished:
                p.justPublished = False
                output += p.pretty_print() + "\n\n"
        self.write_polls_to_file()
        return output

    def display_results(self, p_id: str) -> Optional[str]:
        p = self.get_poll_by_id(p_id)
        if p is None:
            return None
        return p.display_results()
