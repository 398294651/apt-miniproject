from google.appengine.ext import ndb


class Image(ndb.Model):
    image_id = ndb.StringProperty()
    image_blob = ndb.BlobProperty()


class Stream(ndb.Model):
    """Models an individual stream entry."""
    owner = ndb.StringProperty()              
    stream_id = ndb.StringProperty()      
    tags = ndb.StringProperty(repeated=True)
    cover_url = ndb.StringProperty()
    images = ndb.StringProperty(repeated=True)
    views = ndb.IntegerProperty()

    subscribers = ndb.StringProperty(repeated=True)
    # last_access = ndb.DateTimeProperty(auto_now_add=True)

    @classmethod
    def getStream(cls,stream_id):
        # if not user: user = gusers.get_current_user()
        # if not user: return
        stream = cls.query(cls.stream_id == stream_id).fetch()
        return stream[0] if stream else stream

class User(ndb.Model):
    user_id = ndb.StringProperty()
    user_streams = ndb.StringProperty(repeated=True)
    subscribed_streams = ndb.StringProperty(repeated=True)

    @classmethod
    def getUser(cls,user_id):
        # if not user: user = gusers.get_current_user()
        # if not user: return
        user = cls.query(cls.user_id == user_id).fetch()
        return user[0] if user else user
