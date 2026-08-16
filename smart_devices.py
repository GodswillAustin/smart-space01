class LookupDevice:
    def __init__(self):
        pass
    def find_device(self):
        return {
            'action': {
                'turn_on': 100,
                'turn_off': 0
            }
        }

# from database_manager import DatabaseManager, Validator
# import json

# database = DatabaseManager(8240950900)
# validator = Validator(8240950900)
# exprement = database.memory()  

# print(exprement)