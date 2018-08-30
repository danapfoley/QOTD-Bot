import time
import json
import shutil
from typing import List, Dict, Tuple, Optional

MAX_GUESSES = 3

QUESTIONS_FILE_NAME = "questions.json"
OLD_QUESTIONS_FILE_NAME = "questionsHistory.json"


def split_category(q_id: str) -> Tuple[str, str]:
    # Splitting the category from qID.
    # Current format is: "Category"qID
    first_inst, last_inst = q_id.find('"'), q_id.rfind('"')
    category = ""
    if q_id.count('"') == 2 and first_inst == 0 and last_inst != (len(q_id) - 1):
        category = q_id[1:last_inst]
        q_id = q_id[last_inst + 1:]
    return q_id, category


class Question:
    def __init__(self, user_id: str, q_id: str, question_text: str,
                 correct_answers: List[str]=None, category: str =""):
        if correct_answers is None:
            correct_answers = []
        self.user_id: str = user_id
        self.q_id: str = q_id
        self.question_text: str = question_text
        self.correct_answers: List[str] = correct_answers
        self.category: str = category
        self.init_time: float = time.time()
        self.publish_time: float = 0
        self.expire_time: float = 0
        self.published: bool = False
        self.just_published: bool = False
        self.answered_by: List[str] = []
        self.guesses: Dict[str, int] = {}

    # We've established rules for which words/characters shouldn't matter in answers.
    # Here is where those get dealt with
    @staticmethod
    def clean_up_answer(answer: str) -> str:
        answer = answer.lower().strip()
        words = answer.split(' ')
        remove_words = ["a", "an", "the", "and"]
        remove_chars = "'’-,.?!\"/[](){}`~:;"

        stripped_words = [word for word in words if word not in remove_words]
        answer = ' '.join(stripped_words).strip()

        for char in remove_chars:
            answer = answer.replace(char, "")

        answer = answer.strip()
        return answer

    # This is just for determining answer correctness
    # If we add a feature in the future for requiring a list of items to all be matched,
    #   here is where that should be added.
    def validate_answer(self, input_answer: str) -> bool:
        for correct_answer in self.correct_answers:
            match = self.clean_up_answer(correct_answer) == self.clean_up_answer(input_answer)
            if match:
                return True
        return False

    def check_answer(self, user_id, input_answer: str) -> bool:
        if self.validate_answer(input_answer) and user_id not in self.answered_by:
            self.answered_by.append(user_id)
            return True
        return False

    def add_answer(self, new_answer: str):
        self.correct_answers.append(new_answer)

    def remove_answer(self, existing_answer: str) -> bool:
        if existing_answer in self.correct_answers:
            self.correct_answers.remove(existing_answer)
            return True
        else:
            return False

    def set_question_text(self, new_question_text: str) -> bool:
        self.question_text = new_question_text
        return True

    def add_user_who_answered(self, user_id: str) -> bool:
        if user_id in self.answered_by:
            return False
        self.answered_by.append(user_id)
        return True

    def time_to_expire(self) -> bool:
        return self.published and (time.time() - self.publish_time) > 60 * 60 * 18  # 18 hours

    # Display a question with its category and ID in a nicely formatted way
    def pretty_print(self) -> str:
        output = "" if self.category == "" else (self.category + " ")
        output = output + "(" + self.q_id + "): " + self.question_text
        return output

    def pretty_print_with_answer(self) -> str:
        return self.pretty_print() + " : " + (
            " : ".join(self.correct_answers) if len(self.correct_answers) > 0 else "(no answer given)")

    def get_answered_users(self) -> List[str]:
        return self.answered_by

    def count_answers(self) -> int:
        return len(self.answered_by)

    def count_guesses(self) -> int:
        return len(self.guesses)

    # There's probably a better way to do this,
    #   but to make sure that only the newly-published questions get displayed,
    #   we have a justPublished flag that is set when publish is called
    #   and unset when QuestionKeeper.firstTimeDisplay is called.
    def publish(self) -> bool:
        if self.published:
            return False
        else:
            self.published = True
            self.just_published = True
            self.publish_time = time.time()
            return True


class QuestionKeeper:
    def __init__(self):
        self.question_list: List[Question] = []
        self.load_questions_from_file()

    # This only runs on startup to retrieve questions from the persistent file
    def load_questions_from_file(self):
        try:
            file = open(QUESTIONS_FILE_NAME)
        except IOError:
            # If not exists, create the file
            questions_json = {"questions": []}
            file = open(QUESTIONS_FILE_NAME, "w+")
            json.dump(questions_json, file, indent=4)
        file.close()

        with open(QUESTIONS_FILE_NAME) as q_file:
            d = json.load(q_file)
            for q_json in d["questions"]:
                q = Question(q_json["user_id"], q_json["qID"], q_json["questionText"], q_json["correctAnswers"],
                             q_json["category"])
                q.init_time = q_json["initTime"]
                q.publish_time = q_json["publishTime"]
                q.published = q_json["published"]
                q.just_published = q_json["justPublished"]
                q.answered_by = q_json["answeredBy"]
                q.guesses = q_json["guesses"]

                self.question_list.append(q)

    @staticmethod
    def back_up_data() -> Dict[str, str]:
        data = {}

        file = open(QUESTIONS_FILE_NAME)
        data["questions"] = file.read()
        file.close()

        file = open(OLD_QUESTIONS_FILE_NAME)
        data["old-questions"] = file.read()
        file.close()

        return data

    # This is run every time a change occurs to the questionsList data (adding, removing, publishing, guesses being
    # made, etc). If the bot crashes at any point, we shouldn't lose too much history. This comes at the cost of
    # frequent write operations, which get costly as the number of questions active at one time grows
    def write_questions_to_file(self):
        questions_json = {"questions": []}

        for q in self.question_list:
            questions_json["questions"].append(vars(q))

        with open(QUESTIONS_FILE_NAME, 'w') as tempfile:
            json.dump(questions_json, tempfile, indent=4)

        shutil.move(tempfile.name, QUESTIONS_FILE_NAME)

    # When questions expire (not get removed), we insert them into the running history of questions in a persistent file
    @staticmethod
    def write_removed_questions_to_file(removed_questions_list: List[Question]):
        try:
            file = open(OLD_QUESTIONS_FILE_NAME)
            questions_json = json.load(file)
        except IOError:
            # If not exists, create the file
            questions_json = {"oldQuestions": []}
            file = open(OLD_QUESTIONS_FILE_NAME, "w+")
            json.dump(questions_json, file, indent=4)
        file.close()

        for q in removed_questions_list:
            questions_json["oldQuestions"].insert(0, vars(q))

        with open(OLD_QUESTIONS_FILE_NAME, 'w') as tempfile:
            json.dump(questions_json, tempfile, indent=4)

        shutil.move(tempfile.name, OLD_QUESTIONS_FILE_NAME)

    def add_question(self, user_id: str, q_id: str, question_text: str, correct_answers: List[str]=None) -> bool:
        if correct_answers is None:
            correct_answers = []
        q_id, category = split_category(q_id)

        # prevent duplicate IDs
        for q in self.question_list:
            if q_id.lower() == q.q_id.lower():
                return False

        self.question_list.append(Question(user_id, q_id, question_text, correct_answers, category))

        # save new data
        self.write_questions_to_file()
        return True

    def remove_question(self, q_id: str, user_id: str) -> bool:
        q_id, category = split_category(q_id)

        for q in self.question_list:
            if q_id.lower() == q.q_id.lower() and (q.user_id == user_id or user_id == "DEV"):
                self.question_list.remove(q)

                # save new data
                self.write_questions_to_file()
                return True
        return False

    # Adds a new allowed answer for a question. The user_id must be the same as the user who submitted the Q
    def add_answer(self, user_id: str, q_id: str, new_answer: str) -> bool:
        q_id, category = split_category(q_id)

        q = self.get_user_question_by_id(q_id, user_id)

        if q:
            q.add_answer(new_answer)
            self.write_questions_to_file()
            return True
        else:
            return False

    # Complementary to add_answer
    def remove_answer(self, user_id: str, q_id: str, existing_answer: str) -> bool:
        q_id, category = split_category(q_id)

        q = self.get_user_question_by_id(q_id, user_id)

        if q and q.remove_answer(existing_answer):
            self.write_questions_to_file()
            return True
        else:
            return False

    def set_question_text(self, user_id: str, q_id: str, new_question_text: str) -> bool:
        q_id, category = split_category(q_id)

        q = self.get_user_question_by_id(q_id, user_id)
        if q and q.set_question_text(new_question_text):
            self.write_questions_to_file()
            return True
        else:
            return False

    def add_user_who_answered(self, user_id: str, q_id: str) -> bool:
        if self.get_question_by_id(q_id).add_user_who_answered(user_id):
            self.write_questions_to_file()
            return True
        return False

    def get_question_by_id(self, q_id: str) -> Optional[Question]:
        q_id, category = split_category(q_id)

        for q in self.question_list:
            if q_id.lower() == q.q_id.lower():
                return q

        return None

    # Gets a question only if it was submitted by the user in question, None otherwise
    def get_user_question_by_id(self, q_id: str, user_id: str) -> Optional[Question]:
        q_id, category = split_category(q_id)
        q_id = q_id.lower()

        for q in self.question_list:
            if q_id == q.q_id.lower() and (q.user_id == user_id or user_id == "DEV"):
                return q

        return None

    def get_submitter_by_q_id(self, q_id: str) -> Optional[str]:
        q = self.get_question_by_id(q_id)
        if q:
            return q.user_id
        else:
            return None

    # Checks for answer correctness when possible, and returns a string based on how it went.
    # There are many possibilities here. If Python had enums, this would be a little bit cleaner
    def check_answer(self, user_id: str, q_id: str, input_answer: str) -> str:
        q = self.get_question_by_id(q_id)
        if q and q.published:
            # Don't allow guesses after someone has answered already
            if user_id in q.answered_by:
                return "already answered"

            # We want to let users give up on a question,
            #   but thanks to a pesky user demanding that it be possible to have a question
            #   with "I give up" as its answer, we need to make sure we don't interpret a correct answer
            #   as the user giving up
            if input_answer.lower() in ["i give up", "give up", "giveup", "igiveup"] and not q.validate_answer(
                    input_answer):
                q.guesses[user_id] = MAX_GUESSES
                self.write_questions_to_file()
                return "gave up"

            # If we've made it to a point where the user is successfully attempting a guess, increment the counter
            if user_id in q.guesses:
                q.guesses[user_id] += 1
            else:
                q.guesses[user_id] = 1

            # Don't allow guesses beyond the max number allowed
            if q.guesses[user_id] >= MAX_GUESSES + 1:
                self.write_questions_to_file()
                return "max guesses"
            # Manual question validation is a feature in progress, but we still allow it
            elif not q.correct_answers:
                self.write_questions_to_file()
                return "needs manual"
            # Finally, we can check if the answer is actually right
            elif q.check_answer(user_id, input_answer):
                self.write_questions_to_file()
                return "correct"

            self.write_questions_to_file()
            return "incorrect"
        return "not found"

    def list_questions(self) -> str:
        output = ""
        for q in self.question_list:
            if q.published:
                output += q.pretty_print() + "\n"
        return output

    # When a user asks to see the questions in a private channel,
    #   we want to show them a bullet point before every question that they could still attempt
    #   Thus:
    #       -They haven't answered it already
    #       -They weren't the one to submit it
    #       -They haven't reached the max number of guesses
    def list_questions_private(self, user_id: str) -> str:
        output = ""
        for q in self.question_list:
            if q.published:
                if user_id not in q.answered_by \
                        and user_id != q.user_id \
                        and (user_id not in q.guesses or q.guesses[user_id] < MAX_GUESSES):
                    output += "● "
                output += q.pretty_print() + "\n"
        return output

    # Same as listQuestionsPrivate, except we just omit the questions that wouldn't have had a bullet point
    def list_incomplete_questions_private(self, user_id: str) -> str:
        output = ""
        for q in self.question_list:
            if q.published \
                    and user_id not in q.answered_by \
                    and (user_id not in q.guesses or q.guesses[user_id] < MAX_GUESSES):
                output += q.pretty_print() + "\n"
        return output

    # Called by `my-questions`. Displays a user's questions with answers
    def list_questions_by_user(self, user_id: str) -> str:
        output = ""
        for q in self.question_list:
            if q.user_id == user_id:
                output += q.pretty_print_with_answer() + (" (published)" if q.published else "") + "\n"
        return output

    # Expires all questions over a certain age (right now we're using 18 hours) from a specific user.
    # Returns a list of questions that got expired
    def expire_questions(self, user_id: str) -> List[Question]:
        questions_expired = []
        for q in self.question_list:
            if q.time_to_expire() and q.user_id == user_id:
                q.expireTime = time.time()
                questions_expired.append(q)

        self.question_list = [q for q in self.question_list if q not in questions_expired]

        self.write_questions_to_file()
        self.write_removed_questions_to_file(questions_expired)

        return questions_expired

    # Publishes one question
    # Should be made user-exclusive in the future
    def publish_by_id(self, q_id: str) -> str:
        q = self.get_question_by_id(q_id)
        if q:
            if q.publish():
                self.write_questions_to_file()
                return "published"
            else:
                return "already published"
        else:
            return "notFound"

    def publish_all_by_user(self, user_id: str):
        for q in self.question_list:
            if q.user_id == user_id:
                q.publish()
        self.write_questions_to_file()

    # When a question/questions get published
    def first_time_display(self) -> str:
        output = ""
        for q in self.question_list:
            if q.just_published:
                q.just_published = False
                output += q.pretty_print() + "\n"
        self.write_questions_to_file()
        return output

    # Reads from the questions history file, and returns a string of displayed question that expired less than 24
    # hours ago
    @staticmethod
    def get_old_questions_string() -> str:
        try:
            file = open(OLD_QUESTIONS_FILE_NAME)
            old_questions = json.load(file)
        except IOError:
            # If not exists, create the file
            old_questions = {"oldQuestions": []}
            file = open(OLD_QUESTIONS_FILE_NAME, "w+")
            json.dump(old_questions, file, indent=4)
        file.close()

        now = time.time()
        elapsed_time = 60 * 60 * 24  # 24 hours
        response = ""

        for q in old_questions["oldQuestions"]:
            # Questions are inserted at the beginning of the data
            # So it's sorted newer to older
            # Thus if we hit a question older than 24hrs, we can stop searching
            if (now - q["expireTime"]) > elapsed_time:
                break
            response += "" if q["category"] == "" else (q["category"] + " ")
            response += "(" + q["qID"] + "): " + q["questionText"] + " : " + (
                " : ".join(q["correctAnswers"]) if len(q["correctAnswers"]) > 0 else "(no answer given)")

            response += "\n"

        return response
