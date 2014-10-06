import json
import os

import webapp2
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext import blobstore

from models import Stream, User, Image


class ServeHandler(blobstore_handlers.BlobstoreDownloadHandler):
  def get(self):
    blob_key = self.request.get('blob_key')
    if not blobstore.get(blob_key):
      self.error(404)
    else:
      self.send_blob(blob_key)


class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
  def post(self):
    upload = self.get_uploads('filename')[0]

    user_photo = Image(image_id=self.request.get('image_id')
                       ,blob_key=upload.key()
                       ,comments=self.request.get('comments'))
    user_photo.put()

    stream = Stream.getStream(self.request.get('stream_id'))
    stream.images.insert(0,"/svc_serve?blob_key=%s" % user_photo.blob_key)
    stream.last_add = str(user_photo.create_date)
    stream.put()

    self.redirect('/view?'+("stream_id=%s" % self.request.get('stream_id')))


class SubscribeHandler(webapp2.RequestHandler):
    def post(self):
        form = json.loads(self.request.body)

        user = User.getUser(form['user_id'])
        if not user:
            self.response.write(json.dumps( {'error':"User %(user_id)r does not exist" % form} ) )
            return

        user.subscribed_streams = form['streams'] + user.subscribed_streams
        user.put()

        self.response.write(json.dumps({'status': "Subscribed user %(user_id)r to %(streams)s" % form}))


class UnsubscribeHandler(webapp2.RequestHandler):
    def post(self):
      form = json.loads(self.request.body)

      user = User.getUser(form['user_id'])
      if not user:
        self.response.write(json.dumps( {'error':"User %(user_id)r does not exist" % form} ) )
        return

      for strm_id in form['streams']:
        idx = user.subscribed_streams.index(strm_id)
        del user.subscribed_streams[idx]

        stream = Stream.getStream(form['stream_id'])
        if stream:
          idx = stream.subscribers.index(strm_id)
          del stream.subscribers[idx]

      user.put()
      self.response.write(json.dumps({'status': "Unsubscribed user %(user_id)r from %(streams)s" % form}))


class ViewStreamHandler(webapp2.RequestHandler):
    def post(self):
        form = json.loads(self.request.body)        

        stream = Stream.getStream(form['stream_id'])
        if not stream:
            self.response.write(json.dumps({'error': "Stream %(stream_id)r does not exist." % form}))
            return

        stream.views += 1
        stream.put()

        outpages = []
        images = []
        for idx in form['page_range'].split(','):
            if not idx: break
            idx = int(idx)
            if idx >= len(stream.images): continue
            outpages.append(str(idx))
            images.append(stream.images[idx])
        outpages = ','.join(outpages)

        self.response.write(json.dumps({'page_range':outpages,'images':images}))

    
class GetStreamsHandler(webapp2.RequestHandler):
    def post(self):
        form = json.loads(self.request.body)
        user = User.getUser(form['user_id'])

        payload = {'user_streams': [Stream.getStream(stream_id).to_dict() for stream_id in user.user_streams if Stream.getStream(stream_id)]
                   , 'subscribed_streams': [Stream.getStream(stream_id).to_dict() for stream_id in user.subscribed_streams if Stream.getStream(stream_id)]}

        self.response.write(json.dumps(payload))


class CreateStreamHandler(webapp2.RequestHandler):        
    def post(self):
        form = json.loads(self.request.body)

        if User.query(User.user_id == form['user_id']).count() == 0:
            self.response.write(json.dumps( {'error':"User %(user_id)r does not exist" % form} ) )

        if Stream.query(Stream.stream_id == form['stream_id']).count() > 0:
            self.response.write(json.dumps( {'error':"Stream %(stream_id)r already exists" % form} ))

        # Create a new stream
        new_stream = Stream(owner=form['user_id']
                            ,stream_id=form['stream_id']
                            ,tags=form['tags']
                            ,cover_url=form['cover_url'] if 'cover_url' in form else ''
                            ,views=0)
        new_stream.put()

        # Update the user's stream list
        user = User.getUser(form['user_id'])
        user.user_streams.insert(0,form['stream_id'])
        user.put()

        self.response.write(json.dumps({'status': 'Created stream %(stream_id)r' % form}))

def deleteUserStreams(user_id,streams):
  # delete stream references from users list
    user = User.getUser(user_id)
    for sid in streams:
        if sid not in user.user_streams: continue

        idx = user.user_streams.index(sid)
        del user.user_streams[idx]
    user.put()
        
class DeleteStreamsHandler(webapp2.RequestHandler):
    def post(self):
        form = json.loads(self.request.body)

        deleteUserStreams(form['user_id'],form['streams'])
        deleteSubscriptionReferences(form['streams'])

        # Now, delete the streams
        for strm in Stream.query(Stream.stream_id.IN(form['streams'])):
            strm.key.delete()

        self.response.write(json.dumps({'status': "Deleted streams %(streams)r" % form}))

def deleteSubscriptionReferences(streams):
    # delete subscriber stream references
    for user in User.query(User.subscribed_streams.IN(streams)):
        for sid in streams:
            if sid not in user.subscribed_streams: continue

            idx = user.subscribed_streams.index(sid)
            del user.subscribed_streams[idx]
        user.put()
        

class DeleteUserHandler(webapp2.RequestHandler):
    def post(self):
        form = json.loads(self.request.body)        
        usr = User.getUser(form['user_id'])
        if not usr:
            self.response.write(json.dumps({'status': 'User %(user_id)r not found' % form}))
            return

        deleteUserStreams(form['user_id'],usr.user_streams)

        usr.key.delete()
        self.response.write(json.dumps({'status': 'Deleted user %(user_id)r' % form}))

        
class CreateUserHandler(webapp2.RequestHandler):
    def post(self):
        form = json.loads(self.request.body)
                     
        if User.query(User.user_id == form['user_id']).count() > 0:
            self.response.write(json.dumps( {'error':"User %(user_id)r already exists" % form} ))

        user = User(user_id=form['user_id'])
        user.put()

        self.response.write(json.dumps({'status': 'Created new user %(user_id)r' %form}))

# class ServiceHandler(webapp2.RequestHandler):
#     # @classmethod
#     # def method(cls):
#     @classmethod
#     def Dump(cls):
#         return {cls.name+'\'s': [o.to_dict() for o in cls.query()]}

def ListUsers(form):
    return {'Users': [o.to_dict() for o in User.query()]}

def ListImages(form):
    return {'Images': [o.to_dict() for o in Image.query() if o]}

def ListStreams(form):
    return {'streams':[o.to_dict() for o in Stream.query()]}

    
CallHandler = {'list_users':ListUsers,
               'list_streams':ListStreams}

class TestServiceHandler(webapp2.RequestHandler):
    def post(self):
        form = json.loads(self.request.body)

        response = {}
        response['status'] = "OK"
        response['error'] = None

        if form['service'] not in CallHandler:
            response['error'] = "Service %(service)r does not exist!" % form
            response['error'] += " Available services: %s" % CallHandler.keys()
        else:
            try:
                response.update(CallHandler[form['service']](form))
            except KeyError as e:
                response['error'] = "Missing required information %s" % e
            except Exception as e:
                response['error'] = e
        if response['error']: response['status'] = "Query failed."

        self.response.write(json.dumps(response))
