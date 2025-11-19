import redis

# redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)
redis_client = redis.Redis(host="redis", port=6379, decode_responses=True)


if __name__ == "__main__":
    print("Redis connection:", redis_client.ping())