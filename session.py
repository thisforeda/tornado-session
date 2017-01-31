import pickle, uuid, redis
from time import time as _time
from random import randint as rand

class SessionStore (object):
    
    def __init__(self, settings):
        if not hasattr (SessionStore, 'db'):
            
            SessionStore.db = redis.StrictRedis(
                **settings.get (
                    'redis_session',
                    {
                        'host' : '127.0.0.1',
                        'port' : 6379,
                        'password' : None,
                        'db' : 0,
                    })
                )

gen_sessionid = lambda : "_".join([
            "0123456789"[rand(0, 9)],  uuid.uuid4().hex
        ]) 
 
class Session (dict):
    
    SESSION_KEY = 'session'
    
    def __init__(self, req):
        dict.__init__ (self)
        
        # 如果是新会话的话需要客户端设置COOKIE, 否则没有必要
        self._newcookie_ = False
        
        # redis 数据库
        self.redis = SessionStore(req.settings).db
        
        self.load_session_from_db (req)

        # RequestHandler
        self.req = req
        
    def __getitem__ (self, k):
        '''
           这里只是为了可以这样使用 : if self.session ['islogin']:...
           如果不存在 islogin 这个 key 的话会抛出异常, 这样的话,
           如果不存在这个 key 那么会返回 None
        '''
        
        return self.get(k, None)
    
    def load_session_from_db(self, req):
        '''
           根据 cookie 从数据库中提取 session.
           不存在则新建一个会话字典.
        '''
        
        sess_id = req.get_cookie (Session.SESSION_KEY)

        if sess_id :
            
            # 如果cookie中存在 session cookie , 那么
            # 从数据库中读取序列化的值
            sess_data = self.redis.get (sess_id)
            
            if sess_data:
                try :
                    
                    os = pickle.loads (sess_data)
                    
                    # 保存提取出的字典到 self (dict), 并且暂存 session_id
                    self.session_id = sess_id
                    self.update (os)
                    
                    return

                except :
                    pass

        # 否则新建一个会话 id
        self.session_id = gen_sessionid()
        self._newcookie_ = True
        
        return
    
    def save (self, expires = None):
        '''
           expires 是 session 过期时间(以秒计), 默认是一天
        '''
        
        if self.redis.set (self.session_id, pickle.dumps (dict(self))):
            
            #  设置 cookie, 以及 cookie 过期时间,
            #  一开始 expires 以为是过期秒数, 然后发现不论设置多大, 浏览器
            #  cookie 失效日期都是 1970 年, 后来发现原来是 当前 time() + 要保存的秒数
            if self._newcookie_ or expires:

                if expires == None :
                    # session 默认有效时间是一天
                    expires = 24 * 3600

                assert isinstance (expires, int)
                
                #  设置 session_id 在 redis 中的过期时间
                self.redis.expire (self.session_id, expires)
                
                self.req.set_cookie (
                    Session.SESSION_KEY,
                    self.session_id,
                    expires = _time() + expires
                    )

    def clear (self):
        '''
        class IndexHandler(tornado.web.RequestHandler, SessionMixin):
            def method (self):
            
                self.session.clear() # 清空会话信息

                return self.write('session cleared')
        
        '''
        
        delattr (self.req, '_session_')
        
        if self.redis.delete (self.session_id):
            
            self.req.clear_cookie (
                Session.SESSION_KEY
                )

class SessionMixin (object):
    '''
       :: example ::
       
       >>> class IndexHandler(tornado.web.RequestHandler, SessionMixin):
       >>>     def method (self):
       >>> 
       >>>         self.session['name'] = 'RiDiNH'
       >>>         self.session['loggedin'] = True
       >>> 
       >>>         del self.session['loggedin']
       >>>      
       >>>         # 必须在每次改变会话字典后保存, 否则改变将不会保存到数据库
       >>>         self.session.save()
       >>>          
       >>>         username = self.session.get("name", None)
       >>> 
       >>>         self.write('hello %s' % username)
    '''
    
    @property
    def session(self):

        if not hasattr(self, '_session_'):
            self._session_ = Session(self)

        return self._session_
    
