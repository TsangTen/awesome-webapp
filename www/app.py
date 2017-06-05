#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Ten Tsang'

import logging
import asyncio
import os
import json
import time
from datetime import datetime
from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import orm
from coroweb import add_routes, add_static

logging.basicConfig(level=logging.INFO)

def index(request):
	return web.Response(body=b'<h1>Awesome</h1>', content_type='text/html')

'''
@asyncio.coroutine
def init(loop):
	app = web.Application(loop=loop)
	app.router.add_route('Get', '/', index)
	srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', 9000)
	logging.info('server started at http://127.0.0.1:9000...')
	return srv
'''
async def init(loop):
	await orm.create_pool(loop=loop, host='127.0.0.1', port=3306, user='root', password='1qazxsw2', db='awesome')
	app = web.Application(loop=loop, middlewares=[
		logger_factory, response_factory
	])
	init_jinja2(app, filters=dict(datetime=datetime_filter))
	add_routes(app, 'handlers')
	add_static(app)
	srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
	logging.info('server started at http://127.0.0.1:9000...')
	return srv


loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
