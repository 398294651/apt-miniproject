from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from datetime import datetime,timedelta
import urllib


class Image(ndb.Model):
    stream_id = ndb.StringProperty()
    image_id = ndb.StringProperty()
    blob_key = ndb.BlobKeyProperty()
    create_date = ndb.DateTimeProperty(auto_now_add=True)

    @classmethod
    def getImage(cls,img_id):
        img = cls.query(cls.image_id == img_id).fetch()
        return img[0] if img else img

    def delete(self):
        blob_info = blobstore.BlobInfo.get(self.blob_key)
        blob_info.delete()
        self.key.delete()

    @classmethod
    def dump(cls):
        return [{k:v if v is None else (str(v) if not hasattr(v,'__iter__') else map(str,v))
                 for k,v in o.to_dict().items()} for o in cls.query()]

    @classmethod
    def clear(cls):
        for i in cls.query():
            i.delete()
        
    @classmethod
    def exists(cls,image_id):
        return cls.query(cls.image_id == image_id).count() > 0


class Stream(ndb.Model):
    """Models an individual stream entry."""
    user_id = ndb.StringProperty()              
    stream_id = ndb.StringProperty()      
    tags = ndb.StringProperty(repeated=True)
    cover_url = ndb.StringProperty()
    images = ndb.StringProperty(repeated=True)
    views = ndb.DateTimeProperty(repeated=True)
    subscribers = ndb.StringProperty(repeated=True)
    last_add = ndb.DateTimeProperty()

    @classmethod
    def getStream(cls,stream_id):
        # if not user: user = gusers.get_current_user()
        # if not user: return
        stream = cls.query(cls.stream_id == stream_id).fetch()
        return stream[0] if stream else stream

    def addView(self):
        ''' Insert new view and delete views that are too old '''
        self.views.insert(0,datetime.now())
        while (self.views[0] - self.views[-1]) > timedelta(hours=1):
            self.views.pop()
        self.put()

    def addImage(self,image):
        if str(image.blob_key) in self.images:
            return
        image.put()
        self.images.insert(0,str(image.blob_key))
        self.last_add = image.create_date
        self.put()

    def removeImage(self,image_id):
        idx = self.images.index(image_id)
        del self.images[idx]

        image = Image.getImage(blobstore.BlobKey(image_id))
        if image: image.delete()
        self.put()
        
    def addSubscriber(self,user_id):
        if user_id in self.subscribers:
            return
        self.subscribers.insert(0,user_id)
        self.put()

    def removeSubscriber(self,user_id):
        idx = self.subscribers.index(user_id)
        del self.subscribers[idx]
        self.put()

    def delete(self):
        # delete subscriber stream references        
        for user in User.query(User.subscribed_streams == self.stream_id):
            idx = user.subscribed_streams.index(self.stream_id)
            del user.subscribed_streams[idx]

        # delete associated images
        for img in Image.query(Image.stream_id == self.stream_id):
            img.delete()
        self.key.delete()
            
    def dumpStream(self):
        return {k:v if v is None else (str(v) if not hasattr(v,'__iter__') else map(str,v))
                for k,v in self.to_dict().items()}

    @classmethod
    def dump(cls):
        return [{k:v if v is None else (str(v) if not hasattr(v,'__iter__') else map(str,v))
                 for k,v in o.to_dict().items()} for o in cls.query()]

    @classmethod
    def clear(cls):
        for i in cls.query():
            i.delete()

    @classmethod
    def exists(cls,stream_id):
        return cls.query(cls.stream_id == stream_id).count() > 0

            
class User(ndb.Model):
    user_id = ndb.StringProperty()
    user_pw = ndb.StringProperty()    
    user_streams = ndb.StringProperty(repeated=True)
    subscribed_streams = ndb.StringProperty(repeated=True)

    @classmethod
    def getUser(cls,user_id):
        # if not user: user = gusers.get_current_user()
        # if not user: return
        user = cls.query(cls.user_id == user_id).fetch()
        return user[0] if user else user

    def subscribeStream(self,stream_id):
        if stream_id in self.subscribed_streams:
            return
        self.subscribed_streams.insert(0,stream_id)

        stream = Stream.getStream(stream_id)
        if stream: stream.addSubscriber(self.user_id)
        self.put()
        
    def unsubscribeStream(self,stream_id):
        idx = self.subscribed_streams.index(stream_id)
        del self.subscribed_streams[idx]

        stream = Stream.getStream(stream_id)
        if stream: stream.removeSubscriber(self.user_id)
        self.put()        

    def addStream(self,stream):
        if stream.stream_id in self.user_streams:
            return
        # Update the user's stream list
        self.user_streams.insert(0,stream.stream_id)
        stream.put() # only place where a stream should be created in the db
        self.put()

    def removeStream(self,stream_id):
        idx = self.user_streams.index(stream_id)
        del self.user_streams[idx]

        stream = Stream.getStream(stream_id)        
        if stream: stream.delete()
        self.put()

    def delete(self):
        # delete each stream user created
        for stream in Stream.query(Stream.user_id == self.user_id):
            stream.delete()

        # delete the user
        self.key.delete()

    @classmethod
    def dump(cls):
        return [{k:v if v is None else (str(v) if not hasattr(v,'__iter__') else map(str,v))
                 for k,v in o.to_dict().items()} for o in cls.query()]
        
    @classmethod
    def clear(cls):
        for i in cls.query():
            i.delete()

    @classmethod
    def exists(cls,user_id):
        return cls.query(cls.user_id == user_id).count() > 0
