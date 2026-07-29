import boto3

bucket = boto3.client("s3")


def store(amount: int):
    result = bucket.charges.create(amount=amount)
    return result.id
