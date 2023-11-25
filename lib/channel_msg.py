from collections import namedtuple
from json import JSONEncoder


class ChannelMessage:
    def __init__(self, token, uid, name, text):
        self.token, self.uid, self.name, self.text = token, uid, name, text


class ChannelMessageDumper(JSONEncoder):
    def default(self, o):
        return o.__dict__


def channel_message_loader(channel_msg_dict):
    return namedtuple('X', channel_msg_dict.keys())(*channel_msg_dict.values())


def for_test():
    import json

    channel_msg = ChannelMessage('token', 1, 'steve', 'text message')
    channel_msg_json = json.dumps(channel_msg, cls=ChannelMessageDumper)
    print(channel_msg_json)
    channel_msg_obj = json.loads(channel_msg_json, object_hook=channel_message_loader)
    print(channel_msg_obj.uid)


if __name__ == '__main__':
    for_test()
