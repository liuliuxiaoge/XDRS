import webob

import time
from random import random
from oslo.config import cfg
from xdrs import controller
from xdrs.daemon import Daemon
from xdrs import exception

CONF = cfg.CONF

class XdrsController(Daemon):
    def __init__(self, conf):
        self.conf = conf
        """
        注：在这里会把运行参数写在同一个配置文件中；
        """
        self.interval = int(conf.get('interval', 1800))
        self.controller_api = controller.API() 

    def run_forever(self, *args, **kwargs):
        reported = time.time()
        time.sleep(random() * self.interval)
        
        while True:
            begin = time()
            try:
                self.controller_api.dynamic_resource_scheduling(reported)
            except exception.XdrsControllerError:
                msg = _('There are some error in DRS operation.')
                raise webob.exc.HTTPBadRequest(explanation=msg)
            
            elapsed = time() - begin
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)

    def run_once(self, *args, **kwargs):
        begin = reported = time.time()
        try:
            self.controller_api.dynamic_resource_scheduling(reported)
        except exception.XdrsControllerError:
            msg = _('There are some error in DRS operation.')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        elapsed = time.time() - begin