from twilio.rest import Client

client = Client("AC_SID", "AUTH_TOKEN")


def recent_conferences():
    conferences = client.insights.v1.conferences.list(page_size=20)
    return conferences


def recent_summaries():
    summaries = client.insights.v1.call_summaries.list(page_size=20)
    return summaries
