from copy import deepcopy


class DeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count


class InMemoryCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, field, direction):
        reverse = direction == -1
        self.docs.sort(key=lambda doc: doc.get(field, ""), reverse=reverse)
        return self

    async def to_list(self, length):
        return deepcopy(self.docs[:length])


class InMemoryCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query, projection=None):
        for doc in self.docs:
            if self._matches(doc, query):
                return self._project(doc, projection)
        return None

    async def insert_one(self, doc):
        self.docs.append(deepcopy(doc))

    async def update_one(self, query, update):
        for doc in self.docs:
            if self._matches(doc, query):
                if "$set" in update:
                    doc.update(deepcopy(update["$set"]))
                return

    async def delete_one(self, query):
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                self.docs.pop(index)
                return DeleteResult(1)
        return DeleteResult(0)

    def find(self, query, projection=None):
        docs = [
            self._project(doc, projection)
            for doc in self.docs
            if self._matches(doc, query)
        ]
        return InMemoryCursor(docs)

    def _matches(self, doc, query):
        return all(doc.get(key) == value for key, value in query.items())

    def _project(self, doc, projection):
        result = deepcopy(doc)
        if projection:
            for key, include in projection.items():
                if include == 0:
                    result.pop(key, None)
        return result


class InMemoryDB:
    def __init__(self):
        self.users = InMemoryCollection()
        self.decks = InMemoryCollection()
        self.analysis_runs = InMemoryCollection()
        self.auth_tokens = InMemoryCollection()
        self.rate_limits = InMemoryCollection()


class InMemoryClient:
    def close(self):
        pass
