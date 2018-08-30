import QOTDBot as Qb
from typing import List


class FakeSlackClient:

    @staticmethod
    def say(channel: str, response: str):
        Qb.ignore_unused_args(channel)
        print(response)

    @staticmethod
    def react(channel: str, timestamp: str, emoji: str):
        Qb.ignore_unused_args(channel, timestamp)
        print(":" + emoji + ":")

    @staticmethod
    def dev_log(response: str):
        print(response)

    @staticmethod
    def get_direct_channel(user_id: str):
        Qb.ignore_unused_args(user_id)
        return Qb.DEPLOY_CHANNEL

    @staticmethod
    def get_name_by_id(user_id: str):
        Qb.ignore_unused_args(user_id)
        return "Dana Foley"

    @staticmethod
    def parse_bot_commands(events: List[dict]):
        for event in events:
            if event["type"] == "member_joined_channel" and event["channel"] == Qb.QOTD_CHANNEL:
                FakeSlackClient.say(Qb.QOTD_CHANNEL,
                                    "Welcome " + fake_get_reference_by_id(event["user"]) + "! " + Qb.WELCOME_MESSAGE)


def fake_log(response: str):
    Qb.ignore_unused_args(response)
    pass


def fake_get_reference_by_id(user_id: str):
    Qb.ignore_unused_args(user_id)
    return "@dana.foley"


def fake_get_id_from_reference(user_id_reference: str):
    Qb.ignore_unused_args(user_id_reference)
    return Qb.DEVELOPER_ID


if __name__ == "__main__":
    # Overwrite production-based functions
    Qb.log = fake_log
    Qb.get_reference_by_id = fake_get_reference_by_id
    Qb.get_id_from_reference = fake_get_id_from_reference

    Qb.slack_client = FakeSlackClient()

    Qb.question_keeper = Qb.QuestionKeeper()
    Qb.score_keeper = Qb.ScoreKeeper(Qb.slack_client)
    Qb.command_keeper = Qb.CommandKeeper()
    Qb.poll_keeper = Qb.PollKeeper()

    # Remove command restrictions
    for c in Qb.command_keeper.commands_list:
        c.public_only = False
        c.private_only = False

    print("QOTD Bot pretending to be connected and running!")

    input_str = ""
    Qb.slack_client.parse_bot_commands([{
        "type": "member_joined_channel",
        "user": "W06GH7XHN",
        "channel": Qb.QOTD_CHANNEL,
        "channel_type": "G",
        "team": "T8MPF7EHL"
    }])
    while input_str != "exit":
        input_str = input("> ")
        event_to_handle = {"user": Qb.DEVELOPER_ID, "channel": Qb.DEVELOPER_CHANNEL, "text": input_str}

        Qb.command_keeper.handle_event(event_to_handle)
