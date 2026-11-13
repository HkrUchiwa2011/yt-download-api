import logging

from rq import Worker
from rq.serializers import JSONSerializer

from app.jobs import get_queue, get_redis
from app.storage import ensure_storage


def main():
    logging.basicConfig(level=logging.INFO)
    ensure_storage()
    Worker([get_queue()], connection=get_redis(), serializer=JSONSerializer).work()


if __name__ == "__main__":
    main()
