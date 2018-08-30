import random
import traceback

from WellBehavedSlackClient import *

from QuestionKeeper import *
from ScoreKeeper import *
from PollKeeper import *

from Utils import *

# Make keeper objects global. They are initialized in main
slack_client = None
question_keeper = None
score_keeper = None
command_keeper = None
poll_keeper = None

# Add more responses here to be randomly picked
POINT_RESPONSES = ["Correct! I'll give you a point", ":thumbsup:", "Correct! :fast_parrot:"]


def get_name_by_id(user_id: str) -> str:
    # All Slack user IDs start with "U" or "W", by convention
    # So this is an easy check for invalid names
    if not (user_id.startswith('U') or user_id.startswith('W')):
        return user_id

    # Our top priority is to get the name from the score sheet,
    # since we can change that to a person's preference if they don't want to use their display name
    name_from_score_sheet = score_keeper.get_user_name_in_score_sheet(user_id)
    if name_from_score_sheet:
        user_name = name_from_score_sheet
        return user_name

    # Otherwise, we try the cached user list, and as a last resort, do an API call
    return slack_client.get_name_by_id(user_id)


def needs_more_args(channel: str):
    slack_client.say(channel, "This command needs more arguments! Type \"(command) help\" for usage")


def scores(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Print a list of today's scores, and running monthly scores
    Ranked by number of points
    """
    ignore_unused_args(user_id, timestamp)

    args = args_string.split(' ', 1)

    # If a user to get scores for is specified
    if len(args) > 0 and args[0] != "":
        scores_for_user = get_id_from_reference(args[0])

        if get_name_by_id(scores_for_user) != scores_for_user:  # if user name is valid
            response = score_keeper.get_user_scores(scores_for_user)
        else:
            response = "I couldn't find that user. Use `scores help` for usage instructions"

        slack_client.say(channel, response)
        return

    # Otherwise, print scores for everyone
    response = score_keeper.get_today_scores_ranked()
    response += score_keeper.get_total_scores_ranked()
    slack_client.say(channel, response)


def scores_unranked(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Print a list of today's scores, and running monthly scores
    Sorted alphabetically
    """
    ignore_unused_args(user_id, args_string, timestamp)

    response = score_keeper.get_today_scores()
    response += score_keeper.get_total_scores()
    slack_client.say(channel, response)


def question(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Add or modify a new question
    """
    ignore_unused_args(timestamp)

    args_string = args_string.replace("“", "\"").replace("”", "\"")

    if args_string == "":
        needs_more_args(channel)
        return

    category = ""
    if args_string[0] == "\"":
        second_quote_idx = args_string.find("\"", 1)
        if second_quote_idx != -1:
            category = args_string[0:second_quote_idx]
            args_string = args_string[second_quote_idx:]

    args = args_string.split(' ', 1)

    identifier = (category + args[0]) if len(args) > 0 else ""

    if identifier == "remove":
        response = "You probably meant to use `question [identifier] remove`\n"
        slack_client.say(channel, response)
        return

    if len(args) < 2:
        needs_more_args(channel)
        return
    args = args[1].split(" : ")  # no longer holding identifier
    # args should now look like: "question text : answer1 : answer2 : ..."
    #   or "question text"

    if len(args) < 1:
        needs_more_args(channel)
        return

    question_text = args[0].strip()

    if len(args) > 1:
        answers = [answer_text.strip() for answer_text in args[1:]]
    else:
        answers = []

    if question_text == "remove":
        if question_keeper.remove_question(identifier, "DEV" if user_id == DEVELOPER_ID else user_id):
            response = "Okay, I removed that question"
            slack_client.say(channel, response)
            return
        else:
            response = "I couldn't find a question of yours with that ID"
            slack_client.say(channel, response)
            return

    if question_text == "count":
        q = question_keeper.get_user_question_by_id(identifier, "DEV" if user_id == DEVELOPER_ID else user_id)

        if q is None:
            response = "I couldn't find a question of yours with that ID"
            slack_client.say(channel, response)
            return

        num_answers = q.count_answers()
        num_guesses = q.count_guesses()

        response = str(num_answers) + (
            " people" if num_answers != 1 else " person") + " answered question " + q.q_id + " correctly"

        if num_answers > 0:
            response += ":\n"
            response += "\n".join([("-" + get_name_by_id(answered_by_id)) for answered_by_id in q.answered_by])

        response += "\n\n"
        response += str(num_guesses) + (" people" if num_guesses != 1 else " person") + " guessed " + q.q_id \
            + ", and " + str(num_guesses - num_answers) + " didn't guess the right answer"

        if (num_guesses - num_answers) > 0:
            response += ":\n"
            response += "\n".join(
                [("-" + get_name_by_id(guessedID)) for guessedID in q.guesses.keys() if guessedID not in q.answered_by])

        slack_client.say(channel, response)
        return

    if question_text == "author":
        submitter_id = question_keeper.get_submitter_by_q_id(identifier)
        if submitter_id is None:
            slack_client.say(channel, "I couldn't find a question with that ID")
            return
        else:
            slack_client.say(channel, "That question was submitted by " + get_reference_by_id(submitter_id))
            return

    # only get here if a valid question input format is given
    question_added = question_keeper.add_question(user_id=user_id, q_id=identifier, question_text=question_text,
                                                  correct_answers=answers)

    if question_added:
        response = "Okay, I added your question with ID " + identifier + ".\n" \
                   + "Use `publish` to make your questions publicly available, " \
                   + "or `question " + identifier + " remove` to remove it"
        slack_client.say(channel, response)
        if not answers:
            slack_client.say(channel,
                             "Warning: Your question doesn't seem to have a correct answer. Make sure this is "
                             "intended before publishing.")
    else:
        response = "A question with this ID already exists right now. Please use a different one"
        slack_client.say(channel, response)


def add_answer(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Add a possible answer to an existing question
    """
    ignore_unused_args(timestamp)

    args_string = args_string.replace("“", "\"").replace("”", "\"")

    if args_string == "":
        needs_more_args(channel)
        return

    category = ""
    if args_string[0] == "\"":
        second_quote_idx = args_string.find("\"", 1)
        if second_quote_idx != -1:
            category = args_string[0:second_quote_idx]
            args_string = args_string[second_quote_idx:]

    args = args_string.split(' ', 1)

    identifier = (category + args[0]) if len(args) > 0 else ""

    if len(args) < 2:
        needs_more_args(channel)
        return
    args = args[1].split(" : ")  # no longer holding identifier
    # args should now look like: "[answer1, answer2, ...]"
    #   or just "[answer1]"

    if len(args) < 1:
        needs_more_args(channel)
        return

    args = [arg.strip() for arg in args]

    for newAnswer in args:
        if not question_keeper.add_answer(user_id, identifier, newAnswer):
            slack_client.say(channel, "I couldn't find a question of yours with that ID.\n")
            return

    if len(args) > 1:
        slack_client.say(channel,
                         "Okay, I added the answers \"" + "\", \"".join(args) + "\" to your question " + identifier)
    else:
        slack_client.say(channel, "Okay, I added the answer \"" + args[0] + "\" to your question " + identifier)


def remove_answer(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Remove an answer option from an existing question. Must match the existing answer string exactly
    """
    ignore_unused_args(timestamp)

    args_string = args_string.replace("“", "\"").replace("”", "\"")

    if args_string == "":
        needs_more_args(channel)
        return

    category = ""
    if args_string[0] == "\"":
        second_quote_idx = args_string.find("\"", 1)
        if second_quote_idx != -1:
            category = args_string[0:second_quote_idx]
            args_string = args_string[second_quote_idx:]

    args = args_string.split(' ', 1)

    identifier = (category + args[0]) if len(args) > 0 else ""

    if len(args) < 2:
        needs_more_args(channel)
        return

    existing_answer = args[1].strip()  # no longer holding identifier

    q = question_keeper.get_user_question_by_id(identifier, user_id)
    if not q:
        slack_client.say(channel, "I couldn't find a question of yours with that ID.\n")
        return
    if not question_keeper.remove_answer(user_id, identifier, existing_answer):
        slack_client.say(channel,
                         "I couldn't find an answer that matches your input.\n The current answers are: " + ", ".join(
                             q.correct_answers) + "\n Try again with one of those\n")
        return

    slack_client.say(channel, "Okay, I removed the answer \"" + existing_answer + "\" from your question " + identifier)


def edit_question_text(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Set the text of a question to the new input specified
    """
    ignore_unused_args(timestamp)

    args_string = args_string.replace("“", "\"").replace("”", "\"")

    if args_string == "":
        needs_more_args(channel)
        return

    category = ""
    if args_string[0] == "\"":
        second_quote_idx = args_string.find("\"", 1)
        if second_quote_idx != -1:
            category = args_string[0:second_quote_idx]
            args_string = args_string[second_quote_idx:]

    args = args_string.split(' ', 1)

    identifier = (category + args[0]) if len(args) > 0 else ""

    if len(args) < 2:
        needs_more_args(channel)
        return

    new_question_text = args[1].strip()  # no longer holding identifier

    if " : " in new_question_text:
        response = "\nIt looks like you're trying to add an answer to your question text. " + \
                   "This command is only for editing question text. " + \
                   "Please try again without \" : \" in your new text"
        slack_client.say(channel, response)
        return

    if not question_keeper.set_question_text(user_id, identifier, new_question_text):
        slack_client.say(channel, "I couldn't find a question of yours with that ID.\n")
        return

    slack_client.say(channel, "Okay, that question's text is now \"" + new_question_text + "\"")


def questions(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    List all currently active questions.
    If used in a private channel, the list will include bullet points next to unanswered questions
    """
    ignore_unused_args(args_string, timestamp)

    if is_channel_private(channel):
        response = question_keeper.list_questions_private(user_id)
    else:
        response = question_keeper.list_questions()

    if response == "":
        response = "There are no currently active questions"
    else:
        response = "Here are all the currently active questions:\n" + response

    slack_client.say(channel, response)


def questions_remaining(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Similar to `questions`, but any question that has already been answered,
        guessed the max number of times, or was submitted by you, is omitted.
    """
    ignore_unused_args(args_string, timestamp)

    response = question_keeper.list_incomplete_questions_private(user_id)

    if response == "":
        response = "There are no currently active questions that you can answer"
    else:
        response = "Here are all the currently active questions you have yet to get correct or use all your guesses " \
                   "on:\n" + response

    slack_client.say(channel, response)


def remove_question(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Remove an question, published or not.
    Questions that are removed and not expired do not get saved in question history
    """
    if args_string == "":
        needs_more_args(channel)
        return

    args = args_string.split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    question(channel, user_id, identifier + " remove", timestamp)


def my_questions(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    List all questions you've submitted, published or not.
    Includes answers, and thus must be used in a private channel
    """
    ignore_unused_args(args_string, timestamp)

    response = question_keeper.list_questions_by_user(user_id)

    if response == "":
        response = "You have no questions right now. Use `question` to add some"
    else:
        response = "Here are all of your questions:\n" + response

    slack_client.say(channel, response)


def publish(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Publish all questions by a user.
    If question ID given as argument, publish only that question
    """
    ignore_unused_args(timestamp)

    args = args_string.split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    if identifier != "":
        publish_response = question_keeper.publish_by_id(identifier)
        if publish_response == "published":
            response = "Okay, I published question " + identifier + ".\n"
        elif publish_response == "already published":
            response = identifier + " is already published.\n"
        else:
            response = "I couldn't find a question with that ID.\n"
    else:
        question_keeper.publish_all_by_user(user_id)
        response = "Okay, I've published all of your questions\n"

    new_questions = question_keeper.first_time_display()
    if new_questions != "":
        slack_client.say(DEPLOY_CHANNEL, "New questions:\n" + new_questions)

    slack_client.say(channel, response)


def answer(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Guess the answer to a question.
    Checks for correctness, number of guesses,
        and whether or not to validate manually
    """
    ignore_unused_args(timestamp)

    args = args_string.split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    if len(args) < 2:
        needs_more_args(channel)
        return

    input_answer = args[1]  # no longer holding identifier
    check_response = question_keeper.check_answer(user_id, identifier, input_answer)

    if check_response == "correct":
        q_id = question_keeper.get_question_by_id(identifier).q_id  # Calling this to get proper capitalization
        response = random.choice(POINT_RESPONSES) + "\n"

        if not score_keeper.user_exists(user_id):
            score_keeper.add_new_user(user_id)
            score_keeper.add_name_to_user(user_id, get_name_by_id(user_id))

        score_keeper.add_user_point(user_id)
        slack_client.say(POINT_ANNOUNCEMENT_CHANNEL, "Point for " + get_name_by_id(user_id) +
                         ((" on question " + q_id + "!") if q_id != "" else "!")
                         + ("\nThough they are the one who submitted it :wha:..."
                            if user_id == question_keeper.get_submitter_by_q_id(q_id) else ""))

    elif check_response == "incorrect":
        q = question_keeper.get_question_by_id(identifier)
        guesses_left = MAX_GUESSES - q.guesses[user_id]
        response = "Incorrect. You have " + str(guesses_left) + (
            " guesses left.\n" if guesses_left != 1 else " guess left.\n")
        if guesses_left == 0:
            response += ("The correct answers allowed were " if len(q.correct_answers) > 1
                         else "The correct answer was ") \
                        + ", ".join("\"" + a + "\"" for a in q.correct_answers) \
                        + ". If you think your guess(es) should have been correct, contact " \
                        + get_reference_by_id(q.user_id) + ", who submitted the question.\n"

    elif check_response == "gave up":
        q = question_keeper.get_question_by_id(identifier)
        response = ("The correct answers allowed were " if len(q.correct_answers) > 1 else "The correct answer was ") \
            + ", ".join("\"" + a + "\"" for a in q.correct_answers) \
            + ". If you think your guess(es) should have been correct, contact " \
            + get_reference_by_id(q.user_id) + ", who submitted the question.\n"

    elif check_response == "already answered":
        response = "You already answered that question!"

    elif check_response == "max guesses":
        response = "You've already guessed the maximum number of times, " + str(MAX_GUESSES) + "."

    elif check_response == "needs manual":
        user_who_submitted = question_keeper.get_submitter_by_q_id(identifier)
        response = "This question needs to be validated manually. I'll ask " + get_name_by_id(
            user_who_submitted) + " to check your answer."
        direct_user_channel = slack_client.get_direct_channel(user_who_submitted)
        slack_client.say(direct_user_channel, get_name_by_id(user_id) + " has answered \"" + input_answer
                         + "\" for your question,\n" + question_keeper.get_question_by_id(identifier).pretty_print()
                         + "\nIs this correct?\n(I don't know how to validate answers this way yet)")
    else:
        response = "I couldn't find a question with that ID.\n Use `questions` to find the proper ID.\n"

    slack_client.say(channel, response)


def approve(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Award a point for a user on a question of yours.
    In contrast to add-point, this will announce the point in the usual channel,
    and mark the question as answered correctly by the user in question
    """

    args = args_string.split(" ")
    if len(args) < 2:
        needs_more_args(channel)
        return

    referenced_user_id = get_id_from_reference(args[0])
    q_id = args[1]

    q = question_keeper.get_user_question_by_id(q_id, user_id)

    if q is None:
        slack_client.say(channel, "I couldn't find a question of yours with that ID")
        return
    if get_name_by_id(referenced_user_id) == referenced_user_id:  # if user name is invalid
        slack_client.say(channel, "I couldn't find that user")
        return

    if not question_keeper.add_user_who_answered(referenced_user_id, q_id):
        slack_client.say(channel, "It looks like that user has already answered question " + q.q_id + "!")
        return

    # Only get here if the question exists, the user is valid, and we want to give them a point
    if not score_keeper.user_exists(referenced_user_id):
        score_keeper.add_new_user(referenced_user_id)
        score_keeper.add_name_to_user(referenced_user_id, get_name_by_id(referenced_user_id))

    score_keeper.add_user_point(referenced_user_id)

    slack_client.say(POINT_ANNOUNCEMENT_CHANNEL,
                     "Point for " + get_name_by_id(referenced_user_id) +
                     ((" on question " + q_id + "!") if q_id != "" else "!")
                     + ("\nThough they are the one who submitted it :wha:..."
                        if referenced_user_id == question_keeper.get_submitter_by_q_id(q_id) else ""))
    slack_client.react(channel, timestamp, "thumbsup")


def old_questions(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    List all questions that were expired less than 24 hours ago.
    Does not include questions that were removed
    """
    ignore_unused_args(user_id, args_string, timestamp)

    response = question_keeper.get_old_questions_string()

    if response != "":
        response = "Here are all of the questions I found that were expired in the last 24 hours:\n\n" + response
    else:
        response = "I couldn't find any questions that were expired in the last 24 hours"
    slack_client.say(channel, response)


def hello(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Say hi and some basic ID info
    """
    ignore_unused_args(args_string, timestamp)

    response = "Hello " + get_name_by_id(user_id) + ", I'm QOTD Bot!"
    response += "\nYour User ID is: " + user_id + "\nThis channel's ID is: " + channel \
                + "\nUse the `help` command for usage instructions.\n"

    slack_client.say(channel, response)


def change_my_name(channel: str, user_id: str, args_string: str, timestamp: str):
    ignore_unused_args(timestamp)

    new_name = args_string

    if score_keeper.user_exists(user_id):
        old_name = score_keeper.get_user_name_in_score_sheet(user_id)
        score_keeper.set_user_name_in_score_sheet(user_id, new_name)
        slack_client.say(channel, "Okay, I changed your name to " + new_name)
        slack_client.say(DEPLOY_CHANNEL, old_name + " has changed their name to " + new_name)
    else:
        score_keeper.add_new_user(user_id)
        score_keeper.add_name_to_user(user_id, new_name)
        slack_client.say(channel, "Okay, I set your name to " + new_name)


def add_points(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Add a number of points for a mentioned user
    """
    ignore_unused_args(timestamp)

    args = args_string.split(' ')

    if len(args) < 1 or args[0] == "":
        needs_more_args(channel)
        return

    points_for_user = get_id_from_reference(args[0])
    num_points = args[1] if len(args) >= 2 and args[1] != "" else "1"

    if get_name_by_id(points_for_user) == points_for_user:  # if user name is invalid
        slack_client.say(channel, "I couldn't find that user. Use `add-point help` for usage instructions")
        return

    # Get a string of just digits
    num_points_digits_only = "".join([c for c in num_points if c.isdigit()])
    # Add back in a negative sign if one was given
    if num_points != "" and num_points[0] == "-" and num_points_digits_only != "":
        num_points_digits_only = "-" + num_points_digits_only

    if num_points_digits_only == "":
        slack_client.say(channel, "I couldn't interpret " + num_points + " as a number. Try again\n")
        return

    if not score_keeper.user_exists(user_id):
        score_keeper.add_new_user(user_id)
        score_keeper.add_name_to_user(user_id, get_name_by_id(user_id))

    num_points_digits_only = int(num_points_digits_only)
    score_keeper.add_user_points(points_for_user, num_points_digits_only)

    response = "Okay, I gave " + str(num_points_digits_only) + " point" + (
        "s" if num_points_digits_only != 1 else "") + " to " + get_name_by_id(points_for_user)
    slack_client.say(DEPLOY_CHANNEL, response)


def expire_old_questions(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Expire all questions of yours older than 18 hours.
    Posts the expired questions, their answers,
        and a list of users who answered correctly, to the deploy channel.
    """
    ignore_unused_args(args_string, timestamp)

    expired_questions = question_keeper.expire_questions(user_id)
    expired_questions_strings = []
    for q in expired_questions:
        expired_questions_strings.append(q.pretty_print_with_answer())
        if len(q.get_answered_users()) > 0:
            expired_questions_strings.append("    Answered by:")
        for answered_user_id in q.get_answered_users():
            expired_questions_strings.append("        -" + get_name_by_id(answered_user_id))
        expired_questions_strings.append("\n")

    if len(expired_questions) > 0:
        response = "The following questions have expired:\n"
        response += '\n'.join(expired_questions_strings)
        if channel != DEPLOY_CHANNEL:
            slack_client.say(DEPLOY_CHANNEL, response)
    else:
        response = "No questions of yours older than 18 hours were found"

    slack_client.say(channel, response)


def poll(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Create or modify a poll, with poll text and options separated by " : "
    """
    ignore_unused_args(timestamp)

    if args_string == "":
        needs_more_args(channel)
        return

    args = args_string.split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    if identifier == "remove":
        response = "You probably meant to use `poll [identifier] remove`\n"
        slack_client.say(channel, response)
        return

    if len(args) < 2:
        needs_more_args(channel)
        return

    args = args[1].split(" : ")  # no longer holding identifier, question and options split
    question_text = args[0]
    options_list = args[1:]

    options_dict = {}
    for i in range(len(options_list)):
        options_dict[str(i + 1)] = options_list[i]

    if question_text == "remove":
        if poll_keeper.remove_poll(identifier, "DEV" if user_id == DEVELOPER_ID else user_id):
            response = "Okay, I removed that poll"
            slack_client.say(channel, response)
            return
        else:
            response = "I couldn't find a poll of yours with that ID"
            slack_client.say(channel, response)
            return

    if question_text in ["votes", "status", "results", "check"]:
        response = poll_keeper.display_results(identifier)
        if response is None:
            response = "I couldn't find a poll with that ID"
        slack_client.say(channel, response)
        return

    # only get here if a valid poll input format is given
    poll_added = poll_keeper.add_poll(user_id=user_id, p_id=identifier, poll_question_text=question_text,
                                      options=options_dict)

    if poll_added:
        response = "Okay, I added your poll with ID " + identifier + ".\n" \
                   + "It looks like this:\n\n\n" + poll_keeper.get_poll_by_id(identifier).pretty_print() + "\n\n\n" \
                   + "Use `publish-poll` to make your poll publicly available, " \
                   + "or `poll " + identifier + " remove` to remove it"
    else:
        response = "A poll with this ID already exists right now. Please use a different one"

    slack_client.say(channel, response)


def polls(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    List all currently active polls
    """
    ignore_unused_args(user_id, args_string, timestamp)

    response = poll_keeper.list_polls()

    if response == "":
        response = "There are no currently active polls"
    else:
        response = "Here are all the currently active polls:\n" + response

    slack_client.say(channel, response)


def publish_poll(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Publish all of your polls
    If ID given, publish only the poll with that ID
    """
    ignore_unused_args(timestamp)

    args = args_string.split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    if identifier != "":
        publish_response = poll_keeper.publish_by_id(identifier)
        if publish_response == "published":
            response = "Okay, I published poll " + identifier + ".\n"
        elif publish_response == "already published":
            response = identifier + " is already published.\n"
        else:
            response = "I couldn't find a poll with that ID.\n"
    else:
        poll_keeper.publish_all_by_user(user_id)
        response = "Okay, I've published all of your polls\n"

    new_polls = poll_keeper.first_time_display()
    if new_polls != "":
        slack_client.say(DEPLOY_CHANNEL, "New polls:\n" + new_polls)

    slack_client.say(channel, response)


def respond_to_poll(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Vote on a poll.
    Identifier must match poll ID, and the vote must match the corresponding number of the option
    """
    args = args_string.split(' ', 1)
    identifier = args[0] if len(args) > 0 else ""

    if len(args) < 2:
        needs_more_args(channel)
        return

    input_vote = args[1]  # no longer holding identifier
    check_vote = poll_keeper.submit_response(user_id, identifier, input_vote)

    if check_vote == "not found":
        response = "I couldn't find a poll with that ID.\n"
        slack_client.say(channel, response)
        return

    if check_vote == "bad vote":
        response = "I couldn't find an option that matches \"" + identifier + "\".\n"
        slack_client.say(channel, response)
        return

    slack_client.react(channel, timestamp, "thumbsup")


def tell(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Make the bot talk to another user, in the deploy channel.
    The user who says the command is not hidden
    """
    ignore_unused_args(timestamp)

    args = args_string.split(' ', 1)

    if len(args) < 2:
        # Not using the needsMoreArgs function since this is a hidden command and has no help text
        slack_client.say(channel, "this command needs more arguments!")
        return

    user_to_tell = get_id_from_reference(args[0])
    what_to_say = args[1]

    if get_name_by_id(user_to_tell) == user_to_tell:  # if user name is invalid
        slack_client.say(channel, "I couldn't find that user. Use `add-point help` for usage instructions")
        return

    slack_client.say(DEPLOY_CHANNEL,
                     "Hey " + get_reference_by_id(user_id) + ", " + get_reference_by_id(
                         user_id) + " says " + what_to_say)


def dev_tell(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Make the bot speak on behalf of the dev, in a direct chat with a user
    """
    ignore_unused_args(user_id, timestamp)

    args = args_string.split(' ', 1)

    if len(args) < 2:
        # Not using the needsMoreArgs function since this is a hidden command and has no help text
        slack_client.say(channel, "this command needs more arguments!")
        return

    user_to_tell = get_id_from_reference(args[0])
    what_to_say = args[1]

    if get_name_by_id(user_to_tell) == user_to_tell:  # if user name is invalid
        slack_client.say(channel, "I couldn't find that user. Use `add-point help` for usage instructions")
        return

    user_channel = slack_client.get_direct_channel(user_to_tell)

    slack_client.say(user_channel, what_to_say)


def announce(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Make the bot speak on behalf of the dev, to the deploy channel
    """
    ignore_unused_args(channel, user_id, timestamp)

    slack_client.say(DEPLOY_CHANNEL, args_string)


def refresh_user_list(channel: str, user_id: str, args_string: str, timestamp: str):
    """
    Update the user list that caches user name info
    """
    ignore_unused_args(channel, user_id, args_string, timestamp)

    users_json = {}

    users_list = slack_client.api_call("users.list")["members"]
    for member in users_list:
        name = member["profile"]["display_name"]
        if name == "":
            name = member["profile"]["real_name"]
        users_json[member["id"]] = name

    with open(USER_LIST_FILE, 'w') as tempfile:
        json.dump(users_json, tempfile, indent=4)

    shutil.move(tempfile.name, USER_LIST_FILE)


def backup_data(channel: str, user_id: str, args_string: str, timestamp: str):
    ignore_unused_args(user_id, args_string, timestamp)

    question_keeper_data = question_keeper.back_up_data()
    backed_up_questions = question_keeper_data["questions"]
    backed_up_old_questions = json.dumps(json.loads(question_keeper_data["old-questions"]), separators=(",", ":"))

    old_question_text_chunks = chunkify_text(backed_up_old_questions, 20000)

    score_keeper_data = score_keeper.back_up_data()

    slack_client.say(channel, "Scores:\n\n\n" + score_keeper_data)
    slack_client.say(channel, "Questions:\n\n\n" + backed_up_questions)
    slack_client.say(channel, "Old Questions:\n\n\n")
    for chunk in old_question_text_chunks:
        slack_client.say(channel, chunk)


class Command:
    def __init__(self, aliases: List[str], func: Callable, category: str="", help_text: str="",
                 public_only: bool=False, private_only: bool=False, dev_only: bool=False):
        self.aliases: List[str] = aliases
        self.func: function = func
        self.category: str = category
        self.help_text: str = help_text
        self.public_only: bool = public_only
        self.private_only: bool = private_only
        self.dev_only: bool = dev_only


class CommandKeeper:
    def __init__(self):
        self.help_text_dict = {"Misc": []}
        self.commands_list: List[Command] = [
            Command(
                aliases=["points", "score", "scores"],
                func=scores,
                category="Scoring and Points",
                help_text="`scores <@ user>` - prints a list of today's scores and running totals, for `<@ user>` if "
                          "given, for everyone otherwise "
            ),

            Command(
                aliases=["score-unranked", "scores-unranked"],
                func=scores_unranked,
                category="Scoring and Points",
                help_text="`scores-unranked` - prints a list of today's scores and running totals, "
                          "sorted alphabetically instead of by ranking "
            ),

            Command(
                aliases=["q", "question"],
                func=question,
                category="Questions and Answers",
                help_text="`question [identifier] [question] : <answer1> : <answer2> : ...` - creates a question with "
                          "a reference tag `identifier`.\n"
                          + "`question [identifier] remove` - removes the question with the corresponding ID.\n"
                          + "`question [identifier] count` - shows stats on who has answered/guessed a question.\n"
                          + "`question [identifier] author` - says who submitted a question",
                private_only=True
            ),

            Command(
                aliases=["add-answer", "add-answers"],
                func=add_answer,
                category="Questions and Answers",
                help_text="`add-answer  [identifier] [new answer]` - adds a new possible answer for the question with "
                          "the corresponding identifier.\n"
                          + "`add-answers [identifier] [new answer 1] : <new answer 2> : ...` - adds multiple new "
                            "answers for the question with the corresponding identifier",
                private_only=True
            ),

            Command(
                aliases=["remove-answer"],
                func=remove_answer,
                category="Questions and Answers",
                help_text="`remove-answer [identifier] [existing answer]` - removes an answer option from a question. "
                          "Must be matched _exactly_ to work",
                private_only=True
            ),

            Command(
                aliases=["edit", "edit-text", "edit-question-text"],
                func=edit_question_text,
                category="Questions and Answers",
                help_text="`edit [identifier] [new question text]` - sets the text of an existing question to the "
                          "specified input. Does not change answers "
            ),

            Command(
                aliases=["qs", "questions"],
                func=questions,
                category="Questions and Answers",
                help_text="`questions` - prints a list of today's published questions"
            ),

            Command(
                aliases=["questions-remaining"],
                func=questions_remaining,
                category="Questions and Answers",
                help_text="`questions-remaining` - Prints a list of questions that you have yet to answer or use all "
                          "your guesses on "
            ),

            Command(
                aliases=["rq", "remove", "remove-question"],
                func=remove_question,
                category="Questions and Answers",
                help_text="`remove [identifier]` removes the question with the corresponding ID"
            ),

            Command(
                aliases=["my-questions"],
                func=my_questions,
                category="Questions and Answers",
                help_text="`my-questions` - prints a list of your questions, published or not"
            ),

            Command(
                aliases=["publish"],
                func=publish,
                category="Questions and Answers",
                help_text="`publish <identifier>` - publishes the corresponding question if `identifier` given. "
                          + "Publishes all of your questions otherwise."
            ),

            Command(
                aliases=["a", "answer"],
                func=answer,
                category="Questions and Answers",
                help_text="`answer [identifier] [your answer]` - Must be used in a private channel. "
                          + "Checks your `answer` for the corresponding question.",
                private_only=True
            ),

            Command(
                aliases=["approve"],
                func=approve,
                category="Questions and Answers",
                help_text="`approve [@ user] [question ID]` - awards a point for a user on a question of yours."
            ),

            Command(
                aliases=["hi", "hello", "hola"],
                func=hello,
                help_text="`hello` - says hi back and some basic information"
            ),

            Command(
                aliases=["change-my-name", "change-name"],
                func=change_my_name,
                help_text="`change-my-name [new name]` - changes your name to something other than your Slack display "
                          "name "
            ),

            Command(
                aliases=["add-point", "add-points"],
                func=add_points,
                category="Scoring and Points",
                help_text="`add-point(s) [@ user] <# points>` "
                          + "- gives `# points` to `@ user` if specified, 1 point by default",
                public_only=True
            ),

            Command(
                aliases=["expire-old-questions"],
                func=expire_old_questions,
                category="Questions and Answers",
                help_text="`expire-old-questions` - removes all questions published more than 18 hours ago"
            ),

            Command(
                aliases=["old-questions", "expired-questions", "old-answers"],
                func=old_questions,
                category="Questions and Answers",
                help_text="`old-questions` - gets a list of questions that were expired in the last 24 hours"
            ),

            Command(
                aliases=["tell", "say", "trash-talk"],
                func=tell
            ),

            Command(
                aliases=["dev-say", "dev-tell", "dev-talk"],
                func=dev_tell,
                dev_only=True
            ),

            Command(
                aliases=["announce"],
                func=announce,
                dev_only=True
            ),

            Command(
                aliases=["refresh-user-list"],
                func=refresh_user_list,
                dev_only=True
            ),

            Command(
                aliases=["poll", "p"],
                func=poll,
                category="Polls",
                help_text="`poll [identifier] [question] : [option 1] : [option 2] : ...` - creates a poll with a "
                          "reference tag `identifier`.\n"
                          + "`poll [identifier] remove` - removes the poll with the corresponding ID.\n"
                          + "`poll [identifier] votes` - shows current vote counts for a poll."
            ),

            Command(
                aliases=["polls"],
                func=polls,
                category="Polls",
                help_text="`polls` - prints a list of the currently active polls"
            ),

            Command(
                aliases=["publish-poll", "publish-polls"],
                func=publish_poll,
                category="Polls",
                help_text="`publish-poll [identifier]` - publishes your poll with the specified identifier"
            ),

            Command(
                aliases=["respond", "poll-answer", "poll-respond", "answer-poll", "vote"],
                func=respond_to_poll,
                category="Polls",
                help_text="`vote [identifier] [option-number]` - votes on a poll. Use option IDs, not the option's text"
            ),

            Command(
                aliases=["backup-data"],
                func=backup_data,
                dev_only=True
            )
        ]

        # Categorize help text
        for command in self.commands_list:
            if command.help_text == "":
                continue
            if command.category == "" or command.category == "Misc":
                self.help_text_dict["Misc"].append(command.help_text)
            elif command.category in self.help_text_dict.keys():
                self.help_text_dict[command.category].append(command.help_text)
            else:
                self.help_text_dict[command.category] = [command.help_text]
        for category in self.help_text_dict.keys():
            self.help_text_dict[category].sort()

    def help(self, channel: str):
        response = ""

        for category in self.help_text_dict:
            response += "*" + category + "*:\n"
            for help_text in self.help_text_dict[category]:
                for line in help_text.split("\n"):
                    response += "    " + line + "\n\n"
            response += "\n\n"
        response = response[:-2]  # Slice off the last two newlines

        slack_client.say(channel, "Here's a list of commands I know:\n\n" + response)

    def get_command_by_alias(self, alias: str) -> Optional[Command]:
        for cmd in self.commands_list:
            if alias in cmd.aliases:
                return cmd
        return None

    def handle_event(self, event):
        """
        Execute bot command if the command is known
        """
        user_id = event["user"]
        channel = event["channel"]
        if "ts" in event:
            timestamp = event["ts"]
        else:
            timestamp = 0

        # Clean up multiple whitespace characters for better uniformity for all commands
        # e.g. "This   is:       some text" turns into "This is: some text"
        event["text"] = " ".join(event["text"].split())

        split_arguments = event["text"].split(' ', 1)
        command_alias = split_arguments[0].lower()

        # This is the result of @qotd_bot help
        if command_alias == "help":
            self.help(channel)

        cmd = self.get_command_by_alias(command_alias)
        if not cmd:
            # slackClient.say(channel, "Invalid command")
            return

        if len(split_arguments) > 1:
            # This is the result of @qotd_bot [command] help
            if split_arguments[1] == "help":
                slack_client.say(channel, cmd.help_text)
                return

            args = split_arguments[1]  # slice off the command ID, leaving just arguments
        else:
            args = ""

        if cmd.dev_only and user_id != DEVELOPER_ID:
            response = "I'm sorry, " + get_reference_by_id(user_id) + ", I'm afraid I can't let you do that."
            slack_client.say(channel, response)
            return

        if cmd.public_only and is_channel_private(channel):
            slack_client.say(channel, "You can't use this command in a private channel. Use the public channel instead")
            return

        if cmd.private_only and not is_channel_private(channel):
            slack_client.say(channel, "You can't use this command in a public channel. Message me directly instead")
            return

        # If we make it through all the checks, we can actually run the corresponding function
        try:
            cmd.func(channel, user_id, args, timestamp)
        except Exception as e:
            slack_client.dev_log(
                get_name_by_id(event["user"]) + " said: " + event[
                    "text"] + "\nAnd the following error ocurred:\n\n" + str(
                    e) + "\n\n" + traceback.format_exc())


# ----------------------------------

if __name__ == "__main__":

    print("Creating slack client")
    slack_client = WellBehavedSlackClient(SLACK_BOT_TOKEN)

    if slack_client.rtm_connect(with_team_state=False):

        question_keeper = QuestionKeeper()
        score_keeper = ScoreKeeper(slack_client)
        command_keeper = CommandKeeper()
        poll_keeper = PollKeeper()

        print("QOTD Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        slack_client.set_bot_id(slack_client.api_call("auth.test")["user_id"])
        while True:
            # The client can reject our rtm_read call for many reasons
            # So when that happens, we wait 3 seconds and try to reconnect
            # If there is no internet connection, this will continue to loop until there is
            try:
                parsed_event = slack_client.parse_bot_commands(slack_client.rtm_read())
            except BaseException as parsing_error:
                log("Connection Error. Retrying in 3 seconds...")
                log("Exception details: " + str(parsing_error))
                time.sleep(3)
                try:
                    slack_client.rtm_connect(with_team_state=False)
                except BaseException as connection_error:
                    log("Couldn't reconnect :(")
                    log("Exception details: " + str(connection_error))
                    continue
                continue
            if parsed_event:
                command_keeper.handle_event(parsed_event)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
