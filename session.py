import pickle, uuid, redis
from time import time as _time
from random import randint as rand

'''
    simple session for tornado, 100 + code
    usage &_& : Store

       >>> class IndexHandler(tornado.web.RequestHandler, SessionMixin):
       >>>     def method (self):
       >>> 
       >>>         self.session['name'] = 'RiDiNH' # OR self.session.set('name', 'RiDiNH')
       >>>         self.session['loggedin'] = True
       >>> 
       >>>         del self.session['loggedin']
       >>>      
       >>>         # 必须在每次改变会话字典后保存, 否则改变将不会保存到数据库
       >>>         self.session.save() # OR self.session.save(expires=60)
       >>>          
       >>>         username = self.session.get("name", None)
       >>> 
       >>>         self.write('hello %s' % username)

       >>> app = tornado.web.Application (
       >>>     handlers = [ 
       >>>         (r'/t', TT),
       >>>         (r'/e', EE),
       >>>         (r'/c', CC)
       >>>     ],
       >>> 
       >>>     # redis_session 默认设置是 
       >>>     # host:127.0.0.1, port:6379, no password
       >>>     redis_session = dict (
       >>>         host = 'redis server host', 
       >>>         port = 6379, # port
       >>>         db = 0, # db index
       >>>         password = "passwd , (None) no passwd",
       >>>     ),
       >>>     cookie_secret = 'Your Cookie Secret',
       >>>     debug = True,
       >>> )
                                    (C) 2017 RiDiNH.
                                    https://github.com/thisforeda 
'''

#
#    产生一个 session id, 结果是一个随机数 + "_" + uuid4 结果
#    遇到一个相同结果的可能性对我来说可以忽略不计了
#
gen_sessionid = lambda : "_".join([
            "0123456789abcdef"[rand(0, 15)],  uuid.uuid4().hex
        ]) 
 
class Session (dict):
    '''
        Seesion, 属性和字典基本相同
        SESSION_KEY 是存储在客户端中 session cookie 的名称
    '''

    SESSION_KEY = 'session'
    
    def __init__ (self, req):
        
        # 暂存 RequestHandler 用来后续 save()/clear() 使用
        # 如果是新会话的话需要客户端设置COOKIE, 否则不需要
        self._req_ = req
        self._new_session_ = False
        self.application = req.application
        
        # 从数据库中提取 session 信息, 会话将会被 update 到自身
        self._load_session_ (req)

    @property
    def _db_ (self):
        if not hasattr (self.application, '_db_'):
            
            self.application._db_ = redis.StrictRedis(
                ** self._req_.settings.get (
                    'redis_session',
                    {
                        'host' : '127.0.0.1',
                        'port' : 6379,
                        'password' : None,
                        'db' : 0,
                    })
                )

        return self.application._db_
    
    def __getitem__ (self, k):
        '''
           这里只是为了可以这样使用 : if self.session ['islogin']:...
           如果不存在 islogin 这个 key 的话会抛出异常, 这样的话,
           如果不存在这个 key 那么会返回 None
        '''
        try :

            return super (Session, self).__getitem__ (k)
        
        except KeyError:
            return

    def _load_session_ (self, req):
        '''
           根据 cookie 从数据库中提取 session.
           不存在则新建一个会话字典.
        '''
        sess_id = req.get_secure_cookie (Session.SESSION_KEY)

        if sess_id :
            
            # 如果cookie中存在 session cookie , 那么
            # 从数据库中读取序列化的值
            sess_data = self._db_.get (sess_id)
            
            if sess_data:
                try :
                    do = pickle.loads (sess_data)
                    
                    # 保存提取出的字典到 self (dict), 并且暂存 session_id
                    self.session_id = sess_id
                    self.update (do)
                    return

                except Exception:
                    # 如果这中间遇到异常的话会重新生成 session
                    pass

        # 新建一个会话 id 并标记这是一个新会话,
        # 通知 save() 对客户端设置 cookie
        
        self.session_id = gen_sessionid ()
        self._new_session_ = True
        
        return

    def set (self, k, v):
        '''
           self.session.set('key', 'value')
        '''
        self.__setitem__ (k, v)
        
    def save (self, expires = None):
        '''
           expires 是 session 过期时间(以秒计), 默认是一天
        '''
        
        if self._db_.set (self.session_id, pickle.dumps (dict(self))):
            
            #  设置 cookie, 以及 cookie 过期时间,
            #  一开始 expires 以为是过期秒数, 然后发现不论设置多大, 浏览器
            #  cookie 失效日期都是 1970 年, 后来发现是当前 time() + 要保存的秒数
            if self._new_session_ or expires:

                if expires == None :
                    # session 默认有效时间是一天
                    # 24 * 3600 seconds
                    expires = 86400

                assert isinstance (expires, int)
                
                #  设置 session_id 在 redis 中的过期时间
                self._db_.expire (self.session_id, expires)
                
                self._req_.set_secure_cookie (
                    Session.SESSION_KEY,
                    self.session_id,
                    expires = _time () + expires
                    )
    
    def clear (self):
        '''
        class IndexHandler(tornado.web.RequestHandler, SessionMixin):
            def method (self):
            
                self.session.clear() # 清空会话信息
                return self.write('session cleared')
        '''
        
        delattr (self._req_, '_session_')
        
        self._db_.delete (self.session_id)

        # 注意, 由于一些原因,
        # 可能数据库中的会话信息并没有被清除
        self._req_.clear_cookie (
            Session.SESSION_KEY
            )

class SessionMixin (object):
    
    @ property
    def session (self):
        '''
            没有必要每次访问 session 时都重新加载一下,
            所以当存在_session_属性时直接返回会话。
        '''

        if not hasattr (self, '_session_'):
            self._session_ = Session (self)

        return self._session_
