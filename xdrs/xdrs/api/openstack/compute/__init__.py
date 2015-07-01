"""
WSGI middleware for OpenStack Compute API.
"""

from oslo.config import cfg

import xdrs.api.openstack
from nova.api.openstack.compute import consoles
from nova.api.openstack.compute import extensions
from nova.api.openstack.compute import flavors
from nova.api.openstack.compute import image_metadata
from nova.api.openstack.compute import images
from nova.api.openstack.compute import ips
from nova.api.openstack.compute import limits
from nova.api.openstack.compute import plugins
from nova.api.openstack.compute import server_metadata
from nova.api.openstack.compute import servers
from xdrs.api.openstack.compute import versions

allow_instance_snapshots_opt = cfg.BoolOpt('allow_instance_snapshots',
        default=True,
        help='Permit instance snapshot operations.')

CONF = cfg.CONF
CONF.register_opt(allow_instance_snapshots_opt)


class APIRouter(xdrs.api.openstack.APIRouter):
    """
    Routes requests on the OpenStack API to the appropriate controller
    and method.
    """
    ExtensionManager = extensions.ExtensionManager

    """
    还未完成，需要根据具体的API进行修改；
    """
    def _setup_routes(self, mapper, ext_mgr, init_only):
        """
        ======================================================================================
        ext_mgr = <nova.api.openstack.compute.extensions.ExtensionManager object at 0x40a2c10>
        init_only = None
        mapper = Route name Methods Path
        ======================================================================================
        """
        if init_only is None or 'versions' in init_only:
            self.resources['versions'] = versions.create_resource()
            mapper.connect("versions", "/",
                        controller=self.resources['versions'],
                        action='show',
                        conditions={"method": ['GET']})
        """
        ======================================================================================
        mapper = 
        Route name     Methods     Path
        versions       GET         /   
        ======================================================================================
        """

        mapper.redirect("", "/")

        if init_only is None or 'consoles' in init_only:
            self.resources['consoles'] = consoles.create_resource()
            mapper.resource("console", "consoles",
                        controller=self.resources['consoles'],
                        parent_resource=dict(member_name='server',
                        collection_name='servers'))
        """
        ======================================================================================
        mapper = 
        Route name                    Methods Path                                                          
        versions                      GET     /                                                             
                                                                                                                                                                                                
                                      POST    /{project_id}/servers/:server_id/consoles.:(format)           
                                      POST    /{project_id}/servers/:server_id/consoles                     
        formatted_server_consoles      GET     /{project_id}/servers/:server_id/consoles.:(format)           
        server_consoles                GET     /{project_id}/servers/:server_id/consoles                     
        formatted_server_new_console   GET     /{project_id}/servers/:server_id/consoles/new.:(format)       
        server_new_console             GET     /{project_id}/servers/:server_id/consoles/new                 
                                      PUT     /{project_id}/servers/:server_id/consoles/:(id).:(format)     
                                      PUT     /{project_id}/servers/:server_id/consoles/:(id)               
                                      DELETE  /{project_id}/servers/:server_id/consoles/:(id).:(format)     
                                      DELETE  /{project_id}/servers/:server_id/consoles/:(id)               
        formatted_server_edit_console  GET     /{project_id}/servers/:server_id/consoles/:(id)/edit.:(format)
        server_edit_console            GET     /{project_id}/servers/:server_id/consoles/:(id)/edit          
        formatted_server_console       GET     /{project_id}/servers/:server_id/consoles/:(id).:(format)     
        server_console                 GET     /{project_id}/servers/:server_id/consoles/:(id)               
        ======================================================================================
        """

        if init_only is None or 'consoles' in init_only or \
                'servers' in init_only or 'ips' in init_only:
            self.resources['servers'] = servers.create_resource(ext_mgr)
            mapper.resource("server", "servers",
                            controller=self.resources['servers'],
                            collection={'detail': 'GET'},
                            member={'action': 'POST'})
        """
======================================================================================
mapper = 
Route name                    Methods Path                                                          
......           
                              POST    /{project_id}/servers.:(format)                               
                              POST    /{project_id}/servers                                         
formatted_detail_servers      GET     /{project_id}/servers/detail.:(format)                        
detail_servers                GET     /{project_id}/servers/detail                                  
formatted_servers             GET     /{project_id}/servers.:(format)                               
servers                       GET     /{project_id}/servers                                         
formatted_new_server          GET     /{project_id}/servers/new.:(format)                           
new_server                    GET     /{project_id}/servers/new                                     
                              PUT     /{project_id}/servers/:(id).:(format)                         
                              PUT     /{project_id}/servers/:(id)                                   
formatted_action_server       POST    /{project_id}/servers/:(id)/action.:(format)                  
action_server                 POST    /{project_id}/servers/:(id)/action                            
                              DELETE  /{project_id}/servers/:(id).:(format)                         
                              DELETE  /{project_id}/servers/:(id)                                   
formatted_edit_server         GET     /{project_id}/servers/:(id)/edit.:(format)                    
edit_server                   GET     /{project_id}/servers/:(id)/edit                              
formatted_server              GET     /{project_id}/servers/:(id).:(format)                         
server                        GET     /{project_id}/servers/:(id)                                   
======================================================================================
        """

        if init_only is None or 'ips' in init_only:
            self.resources['ips'] = ips.create_resource()
            mapper.resource("ip", "ips", controller=self.resources['ips'],
                            parent_resource=dict(member_name='server',
                                                 collection_name='servers'))
        """
======================================================================================
mapper = 
Route name                    Methods Path                                                          
......                                  
                              POST    /{project_id}/servers/:server_id/ips.:(format)                
                              POST    /{project_id}/servers/:server_id/ips                          
formatted_server_ips          GET     /{project_id}/servers/:server_id/ips.:(format)                
server_ips                    GET     /{project_id}/servers/:server_id/ips                          
formatted_server_new_ip       GET     /{project_id}/servers/:server_id/ips/new.:(format)            
server_new_ip                 GET     /{project_id}/servers/:server_id/ips/new                      
                              PUT     /{project_id}/servers/:server_id/ips/:(id).:(format)          
                              PUT     /{project_id}/servers/:server_id/ips/:(id)                    
                              DELETE  /{project_id}/servers/:server_id/ips/:(id).:(format)          
                              DELETE  /{project_id}/servers/:server_id/ips/:(id)                    
formatted_server_edit_ip      GET     /{project_id}/servers/:server_id/ips/:(id)/edit.:(format)     
server_edit_ip                GET     /{project_id}/servers/:server_id/ips/:(id)/edit               
formatted_server_ip           GET     /{project_id}/servers/:server_id/ips/:(id).:(format)          
server_ip                     GET     /{project_id}/servers/:server_id/ips/:(id)                    
======================================================================================
        """

        if init_only is None or 'images' in init_only:
            self.resources['images'] = images.create_resource()
            mapper.resource("image", "images",
                            controller=self.resources['images'],
                            collection={'detail': 'GET'})
        """
======================================================================================
mapper = 
Route name                    Methods Path                                                          
......                                        
                              POST    /{project_id}/images.:(format)                                
                              POST    /{project_id}/images                                          
formatted_detail_images       GET     /{project_id}/images/detail.:(format)                         
detail_images                 GET     /{project_id}/images/detail                                   
formatted_images              GET     /{project_id}/images.:(format)                                
images                        GET     /{project_id}/images                                          
formatted_new_image           GET     /{project_id}/images/new.:(format)                            
new_image                     GET     /{project_id}/images/new                                      
                              PUT     /{project_id}/images/:(id).:(format)                          
                              PUT     /{project_id}/images/:(id)                                    
                              DELETE  /{project_id}/images/:(id).:(format)                          
                              DELETE  /{project_id}/images/:(id)                                    
formatted_edit_image          GET     /{project_id}/images/:(id)/edit.:(format)                     
edit_image                    GET     /{project_id}/images/:(id)/edit                               
formatted_image               GET     /{project_id}/images/:(id).:(format)                          
image                         GET     /{project_id}/images/:(id)                                    
======================================================================================
        """

        if init_only is None or 'limits' in init_only:
            self.resources['limits'] = limits.create_resource()
            mapper.resource("limit", "limits",
                            controller=self.resources['limits'])
        """
======================================================================================
mapper = 
Route name                    Methods Path                                                          
......                                
                              POST    /{project_id}/limits.:(format)                                
                              POST    /{project_id}/limits                                          
formatted_limits              GET     /{project_id}/limits.:(format)                                
limits                        GET     /{project_id}/limits                                          
formatted_new_limit           GET     /{project_id}/limits/new.:(format)                            
new_limit                     GET     /{project_id}/limits/new                                      
                              PUT     /{project_id}/limits/:(id).:(format)                          
                              PUT     /{project_id}/limits/:(id)                                    
                              DELETE  /{project_id}/limits/:(id).:(format)                          
                              DELETE  /{project_id}/limits/:(id)                                    
formatted_edit_limit          GET     /{project_id}/limits/:(id)/edit.:(format)                     
edit_limit                    GET     /{project_id}/limits/:(id)/edit                               
formatted_limit               GET     /{project_id}/limits/:(id).:(format)                          
limit                         GET     /{project_id}/limits/:(id)                                    
======================================================================================
        """

        if init_only is None or 'flavors' in init_only:
            self.resources['flavors'] = flavors.create_resource()
            mapper.resource("flavor", "flavors",
                            controller=self.resources['flavors'],
                            collection={'detail': 'GET'},
                            member={'action': 'POST'})
        """
======================================================================================
mapper = 
Route name                    Methods Path   
......                                                                              
                              POST    /{project_id}/flavors.:(format)                               
                              POST    /{project_id}/flavors                                         
formatted_detail_flavors      GET     /{project_id}/flavors/detail.:(format)                        
detail_flavors                GET     /{project_id}/flavors/detail                                  
formatted_flavors             GET     /{project_id}/flavors.:(format)                               
flavors                       GET     /{project_id}/flavors                                         
formatted_new_flavor          GET     /{project_id}/flavors/new.:(format)                           
new_flavor                    GET     /{project_id}/flavors/new                                     
                              PUT     /{project_id}/flavors/:(id).:(format)                         
                              PUT     /{project_id}/flavors/:(id)                                   
formatted_action_flavor       POST    /{project_id}/flavors/:(id)/action.:(format)                  
action_flavor                 POST    /{project_id}/flavors/:(id)/action                            
                              DELETE  /{project_id}/flavors/:(id).:(format)                         
                              DELETE  /{project_id}/flavors/:(id)                                   
formatted_edit_flavor         GET     /{project_id}/flavors/:(id)/edit.:(format)                    
edit_flavor                   GET     /{project_id}/flavors/:(id)/edit                              
formatted_flavor              GET     /{project_id}/flavors/:(id).:(format)                         
flavor                        GET     /{project_id}/flavors/:(id)                                   
======================================================================================
        """

        if init_only is None or 'image_metadata' in init_only:
            self.resources['image_metadata'] = image_metadata.create_resource()
            image_metadata_controller = self.resources['image_metadata']

            mapper.resource("image_meta", "metadata",
                            controller=image_metadata_controller,
                            parent_resource=dict(member_name='image',
                            collection_name='images'))
            """
======================================================================================
mapper = 
Route name                      Methods Path                                                          
......
                                POST    /{project_id}/images/:image_id/metadata.:(format)             
                                POST    /{project_id}/images/:image_id/metadata                       
formatted_image_metadata        GET     /{project_id}/images/:image_id/metadata.:(format)             
image_metadata                  GET     /{project_id}/images/:image_id/metadata                       
formatted_image_new_image_meta  GET     /{project_id}/images/:image_id/metadata/new.:(format)         
image_new_image_meta            GET     /{project_id}/images/:image_id/metadata/new                   
                               PUT     /{project_id}/images/:image_id/metadata/:(id).:(format)       
                               PUT     /{project_id}/images/:image_id/metadata/:(id)                 
                               DELETE  /{project_id}/images/:image_id/metadata/:(id).:(format)       
                               DELETE  /{project_id}/images/:image_id/metadata/:(id)                 
formatted_image_edit_image_meta GET     /{project_id}/images/:image_id/metadata/:(id)/edit.:(format)  
image_edit_image_meta           GET     /{project_id}/images/:image_id/metadata/:(id)/edit            
formatted_image_image_meta      GET     /{project_id}/images/:image_id/metadata/:(id).:(format)       
image_image_meta                GET     /{project_id}/images/:image_id/metadata/:(id)                 
======================================================================================
            """

            mapper.connect("metadata",
                           "/{project_id}/images/{image_id}/metadata",
                           controller=image_metadata_controller,
                           action='update_all',
                           conditions={"method": ['PUT']})
            """
======================================================================================
mapper = 
Route name                      Methods Path                                                          
......                
metadata                        PUT     /{project_id}/images/{image_id}/metadata                      
======================================================================================
            """

        if init_only is None or 'server_metadata' in init_only:
            self.resources['server_metadata'] = \
                server_metadata.create_resource()
            server_metadata_controller = self.resources['server_metadata']

            mapper.resource("server_meta", "metadata",
                            controller=server_metadata_controller,
                            parent_resource=dict(member_name='server',
                            collection_name='servers'))
            """
======================================================================================
mapper = 
Route name                        Methods Path                                                          
......                     
                                  POST    /{project_id}/servers/:server_id/metadata.:(format)           
                                  POST    /{project_id}/servers/:server_id/metadata                     
formatted_server_metadata         GET     /{project_id}/servers/:server_id/metadata.:(format)           
server_metadata                   GET     /{project_id}/servers/:server_id/metadata                     
formatted_server_new_server_meta  GET     /{project_id}/servers/:server_id/metadata/new.:(format)       
server_new_server_meta            GET     /{project_id}/servers/:server_id/metadata/new                 
                                  PUT     /{project_id}/servers/:server_id/metadata/:(id).:(format)     
                                  PUT     /{project_id}/servers/:server_id/metadata/:(id)               
                                  DELETE  /{project_id}/servers/:server_id/metadata/:(id).:(format)     
                                  DELETE  /{project_id}/servers/:server_id/metadata/:(id)               
formatted_server_edit_server_meta GET     /{project_id}/servers/:server_id/metadata/:(id)/edit.:(format)
server_edit_server_meta           GET     /{project_id}/servers/:server_id/metadata/:(id)/edit          
formatted_server_server_meta      GET     /{project_id}/servers/:server_id/metadata/:(id).:(format)     
server_server_meta                GET     /{project_id}/servers/:server_id/metadata/:(id)               
======================================================================================
            """

            mapper.connect("metadata",
                           "/{project_id}/servers/{server_id}/metadata",
                           controller=server_metadata_controller,
                           action='update_all',
                           conditions={"method": ['PUT']})
            """
======================================================================================
mapper = 
Route name                        Methods Path                                                          
......            
metadata                          PUT     /{project_id}/servers/{server_id}/metadata                    
======================================================================================
            """