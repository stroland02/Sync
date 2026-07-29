import slack_sdk

client = slack_sdk.WebClient(token="unused-in-a-fixture")


def post(channel: str, text: str):
    return client.chat_postMessage(channel=channel, text=text)
