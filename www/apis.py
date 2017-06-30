#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Ten Tsang'

'''
JSON API definition
'''

import json
import logging
import inspect
import functools

class APIError(Exception):
	'''
		the base APIError which contains error(required), data(optional) and message(optional).
	'''
	
	def __init__(self, error, data='', message=''):
		super(APIError, self).__init__(message)  # 初始化父类
		self.error = error
		self.data = data
		self.message = message


class APIValueError(APIError):
	'''
		Indicate the input value has error or invalid.
		The data specifies the error field of input form.
	'''
	
	def __init__(self, field, message=''):
		super(APIValueError, self).__init__('value:invalid', field, message)


class APIResourceNotFoundError(APIError):
	'''
		Indicate the resource was not found.
		The data specifies the resource name.
	'''
	
	def __init__(self, field, message=''):
		super(APIResourceNotFoundError, self).__init__('value:notfound', field, message)


class APIPermissionError(APIError):
	'''
		Indicate the api has no permission.
	'''
	
	def __init__(self, message):
		super(APIPermissionError, self).__init__('permission:forbidden', 'permission', message)

class Page(object):
	'''
		Page object for display pages.
	'''
	def __init__(self, item_count, page_index=1, page_size=10):
		self.item_count = item_count  # 博客总数量
		self.page_size = page_size  # 每页显示博客篇数
		# 计算页数
		self.page_count = item_count // page_size + (1 if item_count % page_size > 0 else 0)
		if (item_count == 0) or (page_index > self.page_count):  # 如果没有博客，或页面索引大于页数
			self.offset = 0  # 分页的开端，本页从第几篇文章开始
			self.limit = 0  # 分页的结尾，本页最后一篇文章的索引
			self.page_index = 1
		else:
			self.page_index = page_index
			self.offset = self.page_size * (page_index - 1)
			self.limit = self.page_size
		self.has_next = self.page_index < self.page_count  # 存在下一页
		self.has_previous = self.page_index > 1  #  存在上一页

	def __str__(self):  # 如果要把一个类的实例变成str，就需要实现特殊方法__str__()
		return 'item_count: %s, page_count: %s, page_index: %s, page_size: %s, offset: %s, limit: %s' % (self.item_count, self.page_count, self.page_index, self.page_size, self.offset, self.limit)

	__repr__ = __str__  # 偷懒的定义__repr__的方法

	# Python 定义了__str__()和__repr__()两种方法，
	# __str__()用于显示给用户，
	# 而__repr__()用于显示给开发人员。
		








