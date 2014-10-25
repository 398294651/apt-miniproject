

##############################################
# Simple testrunner for google appengine
#  Based on stub provided by Adnan Aziz
# Does not run unit tests.
# For unit test integration, read the google appengine tutorials:
#  https://developers.google.com/appengine/docs/python/tools/localunittesting
# For functional testing (I think that's what it's called):
#  https://developers.google.com/appengine/docs/python/tools/handlertesting
##############################################
# FILE: testrunner_simple.py
import json
import httplib
import urllib

# Ignore this comment blob for getting started. This was just some useful info I stumbled over
# if using urllib or urllib2  disable proxy settings to run on localhost
#import urllib2
#proxy_support = urllib2.ProxyHandler({})
#opener = urllib2.build_opener(proxy_support)
#print opener.open("http://localhost:8080/").read()
#
globals = {
    "server": "localhost"
    ,"port"  : "8080"
    # "server": "apt-miniproject-fall14.appspot.com"
    # ,"port": None
    # prepare request header
    ,"headers": {"Content-type": "application/json"}}


def send_request(url, req):
    conn = httplib.HTTPConnection(globals["server"],globals["port"])

    print "json request:", json.dumps(req)

    conn.request("POST", url, json.dumps(req), {'headers':globals["headers"]})
    resp = conn.getresponse()

    print "status:", resp.status, resp.reason
    jsonresp = json.loads(resp.read())

    return jsonresp


def test1():
    service = 'delete_stream'
    serviceUrl = '/services'

    helper = lambda kwargs: send_request('/services',kwargs)

    try:
        print
        print "Create users"
        print
        print helper({'service':'create_user','user_id':'tgar'})
        print helper({'service':'create_user','user_id':'tgar2'})

        print
        print "Create streams"
        print helper({'service':'create_stream','user_id':'tgar2','stream_id':'meow','tags':['#catdance','#buddymovies']})
        print helper({'service':'create_stream','user_id':'tgar2','stream_id':'meow2','tags':['#buddymovies']})

        print
        print "Subscribe"
        print helper({'service':'subscribe','user_id':'tgar','streams':['meow']})

        print
        print "Delete stream and check if they've been removed"
        print helper({'service':'delete_streams','streams':['meow']})
        print helper({'service':'view_stream','stream_id':'meow'})
        print helper({'service':'get_streams','user_id':'tgar'})
        print helper({'service':'get_streams','user_id':'tgar2'})

        print
        print helper({'service':'delete_streams','streams':['meow2']})
        print helper({'service':'delete_user','user_id':'tgar'})
        print helper({'service':'delete_user','user_id':'tgar2'})
    except Exception as e:
        print e


if __name__ == '__main__':
  test1()
  









