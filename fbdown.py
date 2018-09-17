from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import time
import json
import re
import os

import itertools

import urllib.request

import arrow

from collections import defaultdict

class Fbdown:

	def __init__(self, wait=30, post_dir='posts', video_dir='videos', picture_dir='pictures',
						creds_dir='credentials'):

		self.wait = wait

		self.today = arrow.utcnow().to('Australia/Sydney').format('YYYY-MM-DD')

		options = webdriver.ChromeOptions()
		options.add_argument('disable-notifications')

		self.driver = webdriver.Chrome('webdriver/chromedriver', chrome_options=options)

		self.fbid_re = re.compile(r'(?<=p.)\d+')	
		self.vidid_re = re.compile(r'(?<=videos\/)\d+(?=\/)')

		self.reactions = 'like love haha wow sad angry'.split()
		self.extensions = {'video': ['mp4'], 'picture': ['jpg', 'png']}

		self.video_dir = video_dir
		self.picture_dir = picture_dir
		self.post_dir = post_dir
		self.creds_dir = creds_dir

		if not os.path.exists(self.creds_dir):
			self.driver.close()
			raise Exception('can\'t find the credentials directory!')

		for d in [self.post_dir, self.video_dir, self.picture_dir]:
			if not os.path.exists(d):
				os.mkdir(d)
		try:
			self.posts = json.load(open(os.path.join(self.post_dir, 'posts.json')))
			print(f'found a post collection with {len(self.posts)} posts...')
		except:
			self.posts = defaultdict(lambda: defaultdict())
			print('starting a new post collection...')

	def login(self):
		"""
		read credentials from a JSON file and log into your account
		"""

		try:
			LOGIN = json.load(open(f'{self.creds_dir}/facebook.json'))
		except:
			raise IOError('can\'t find the credentials file!')
		else:
			if not all([_ in LOGIN for _ in 'url user password'.split()]):
				raise ValueError('missing keys in the credentials file!')

		self.driver.get(LOGIN['url'])
		self.driver.find_element_by_name('email').send_keys(LOGIN['user'])
		self.driver.find_element_by_name('pass').send_keys(LOGIN['password'])

		# find the right button to click, depending on what variation of the login page you're on

		btn_ = None

		try:
			btn_ = WebDriverWait(self.driver, self.wait) \
							.until(EC.element_to_be_clickable((By.ID, 'loginbutton'))) 
		except:
			pass

		if not btn_:
			try:
				btn_ = WebDriverWait(self.driver, self.wait) \
							.until(EC.element_to_be_clickable((By.XPATH, '[//button[@type="submit"]]')))
			except:
				pass

		if not btn_:
			raise Exception('can\'t find the login button!')
		else:
			btn_.click()

			# wait until the Fundraisers option (presumably, the last on the list of options) on the left panel 
			# becomes clickable

			try:
				WebDriverWait(self.driver, self.wait).until(EC.element_to_be_clickable((By.XPATH, '//a[@title="Fundraisers"]')))
			except:
				raise Exception('page after login has been loading too slow...')

		return self

	def _get_post_info(self, a):

		post_url = a.get_attribute('href')

		post_id = None

		# post id is a part of post url so we just extract it
		try:
			post_id = self.fbid_re.search(post_url).group(0)
		except:
			try:
				aria_tx_ = a.get_attribute('aria-label')
				if 'Video' in aria_tx_:
					try:
						post_id = self.vidid_re.search(post_url).group(0)
					except:
						pass
			except:
				pass

		return {post_id: {'post_url': post_url}}

	def scroll2(self):

		try:
			_ = WebDriverWait(self.driver, self.wait) \
								.until(EC.presence_of_element_located((By.XPATH, 
									'//div[@id="initial_browse_result"]/div[@id="pagelet_loader_initial_browse_result"]/div/div')))
		except:
			raise Exception('couldn\'t find the initial browse result div!')

		while 1:

			self.driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight);")

			d = _.find_element_by_xpath('child::div').find_elements_by_xpath('descendant::a[@href and @rel="theater"]')

			for a in d:
				print(a.get_attribute('href'))
				self.driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight);")

			d = _.find_element_by_xpath('child::div').find_element_by_xpath('following-sibling::div').find_elements_by_xpath('descendant::a[@href and @rel="theater"]')
			
		return self


	def scroll_and_collect(self, max_items=10):

		for block_xpath in ['//div[@id="BrowseResultsContainer"]/div/div/div/a[@href]',
								'//div[@data-testid="paginated_results_pagelet"]/div/div/div/div/a[@href]']:
			for _ in self.driver.find_elements_by_xpath(block_xpath):

				new_post_ = self._get_post_info(_)  # {post_id: {}}

				if set(new_post_) & set(self.posts):
					# no need to update, we have this post info already
					pass
				else:
					self.posts.update()

		hight_ = self.driver.execute_script("return document.body.scrollHeight")

		c = 0

		while len(self.posts) <= max_items:

			self.driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight);")
			time.sleep(5)

			for _ in self.driver.find_elements_by_xpath(f'//div[@id="fbBrowseScrollingPagerContainer{c}"]/div/div/div/div/a[@href]'):

				new_post_ = self._get_post_info(_)

				if set(new_post_) & set(self.posts):
					pass
				else:
					self.posts.update(new_post_)

			print(f'collected urls so far: {len(self.posts)}')

			new_height = self.driver.execute_script("return document.body.scrollHeight")

			if new_height > hight_:
				hight_ = new_height
			else:
				print('reached the bottom of the page')
				break

			c += 1

		return self

	def scroll_and_collect_video(self, max_items=47):

		hight_ = self.driver.execute_script("return document.body.scrollHeight")
		print('starting height is ', hight_)

		print('scrolling...')

		while 1:

			self.driver.execute_script(f"window.scrollTo(0, {hight_ + 200});")
			
			time.sleep(3)

			new_height = self.driver.execute_script("return document.body.scrollHeight")
			
			print('now height is ', new_height)

			if new_height != hight_:
				hight_ = new_height
			else:
				print('reached the bottom of the page')
				break

		while len(self.posts) <= max_items:

			for i, _ in enumerate(self.driver.find_elements_by_xpath('//div[@role="VIDEOS"]'), 1):
				print('i=', i)
				self.posts.update(self._get_post_info(_.find_element_by_xpath('descendant::a[@aria-label]')))
				# r = _.find_element_by_xpath('//abbr[@data-utime]')
				# posted = arrow.get(r.get_attribute('data-utime')).format('YYYY-MM-DD')
				# print(f'posted on {posted}')
		print(f'collected {len(self.posts)} videos')
				
		return self

	def _get_metrics(self):

		"""
		assuming you're ON THE POST PAGE, pick up reactions, comments and shares and return as a dictionary; 
		the dictionary is supposed to look like 
			{'metrics': {'2019-09-10': {'comments': 3, 'shares': 8, ...}}
		"""

		dict_ = defaultdict(lambda: defaultdict(lambda: defaultdict()))

		for _ in self.driver.find_elements_by_xpath('//a[@role="button"]'):

			# search for comments or shares, they may sit in text
			tx_ = _.text.lower()

			if tx_:
				for m in ['comments', 'shares']:
					m_line = re.search(r'\d+\s+(?=' + f'{m})', tx_)
					if m_line:
						dict_['metrics'][self.today][m] = int(m_line.group(0))

			try:
				aria_tx_ = _.get_attribute('aria-label').lower().strip()
				
				for m in self.reactions:
					m_line = re.search(r'\d+\s+(?=' + f'{m})', aria_tx_)
					if m_line:
						dict_['metrics'][self.today][m + 's'] = int(m_line.group(0))
			except:
				continue

		return dict_

	def get_post_details(self, post_url):

		"""
		given a url to the post page, go there and pick up some post details, such as all metrics and date posted;
		return these as a dictionary
		"""

		self.driver.get(post_url)

		d = defaultdict(lambda: defaultdict(lambda: defaultdict()))

		try:
			d['when_posted'] = arrow.get(WebDriverWait(self.driver, self.wait) \
								.until(EC.visibility_of_element_located((By.XPATH, '//abbr[@title and @data-utime]'))) \
									.get_attribute('data-utime')) \
									.format('YYYY-MM-DD')
		except:
			# if a post has no timestamp, it's useless
			print('WARNING: found a post without a timestamp!')
			return d

		d.update(self._get_metrics())

		# find content url, first for pictures
		try:
			curl_ = self.driver.find_element_by_class_name('spotlight').get_attribute('src')
		except:
			pass

		# now try for videos
		try:

			ActionChains(self.driver) \
					.move_to_element(self.driver.find_element_by_xpath('//video[@src]')) \
					.context_click() \
					.perform()

			curl_ = self.driver.find_element_by_xpath('//span[@value]').get_attribute('value')			
		except:
			pass

		d['content_url'] = curl_

		return d

	def get_mob_post(self, post_url):
		"""
		get direct video url 
		https://www.facebook.com/abccoffscoast/videos/2117273828315294/
		https://m.facebook.com
		"""

		self.driver.get(post_url.replace('www', 'm'))

		try:
			_ = self.driver.find_element_by_xpath('//div[@data-sigil="inlineVideo"]')
		except:
			try:
				_ = self.driver.find_element_by_xpath('//div[@data-sigil="photo-image"]')
			except:
				return {'content_url': None}

		# this data-store looks like a dictionary but it's a string
		ds_ = json.loads(_.get_attribute('data-store'))

		url = ds_['src']

		return {'content_url': url}


	def search(self, tag, what='photos', month=None, year=None):
		"""
		search by tag and then filter by date; for photos there's an option to select specific month and year, 
		but for videos you can pick the year only
		"""
		try:
			WebDriverWait(self.driver, self.wait) \
							.until(EC.element_to_be_clickable((By.XPATH, '//input[@placeholder="Search"]'))) \
								.send_keys(tag)
		except:
			raise Exception('couldn\'t find the search field up the top!')

		try:
			WebDriverWait(self.driver, self.wait) \
							.until(EC.element_to_be_clickable((By.XPATH, '//button[@type="submit"]'))) \
								.click()
		except:
			raise Exception('couldn\'t click the submit button!')

		try:
			WebDriverWait(self.driver, self.wait) \
							.until(EC.visibility_of_element_located((By.XPATH, '//div[@role="heading" and @aria-level="3"]')))
		except:
			if self.driver.find_element_by_class_name('clearfix'):
				raise Exception('couldn\'t find anything...')
			else:
				raise Exception('couldn\'t find anything but no nothing found icon either!')

		# not it's time to click on Photos or Videos in the panel menu
		WebDriverWait(self.driver, self.wait) \
					.until(EC.element_to_be_clickable((By.XPATH, f'//li[@data-edge="keywords_blended_{what}"]/a[@href]'))) \
					.click()

		if what == 'photos':
			try:
				WebDriverWait(self.driver, self.wait) \
						.until(EC.visibility_of_element_located((By.XPATH, '//div[text()="Public photos"]')))
			except:
				raise Exception('no Public Photos section!')

		elif what == 'videos':
			try:
				WebDriverWait(self.driver, self.wait) \
					.until(EC.presence_of_element_located((By.XPATH, '//div[@role="VIDEOS"]')))
			except:
				raise Exception('can\'t see a single video in search results!')
		else:
			raise ValueError('you have to choose either photos or videos!')

		date_posted = WebDriverWait(self.driver, self.wait) \
					.until(EC.visibility_of_element_located((By.XPATH, '//h4[text()="DATE POSTED"]')))

		# check what date options are available; you'd expect to see something like ['any date', '2018', '2017', '2016']
		# note that the select month/year option won't appear on this list

		opts_ = date_posted.find_elements_by_xpath('../a[@role="radio"]')
		opts_tx =[_.text.lower().strip() for _ in date_posted.find_elements_by_xpath('../a[@role="radio"]')]

		if (not month) and (str(year) in opts_tx):

			try:
				opts_[opts_tx.index(str(year))].click()
			except:
				raise Exception(f'couldn\'t click on year {year} in Date Posted!')

		elif month and year and (what == 'photos'):

			try:
				date_posted.find_element_by_xpath('../div[@role="radio"]').click()
			except:
				pass

			try:
				m_selector, y_selector = date_posted.find_elements_by_xpath('../descendant::a[@rel="toggle"]')
			except:
				raise ValueError('can\'t find the month and year selectors!')
		
			m_selector.click()

			WebDriverWait(self.driver, self.wait) \
						.until(EC.visibility_of_element_located((By.XPATH, 
							f'//ul[@role="menu"]/li/a/span/span[text()=\"{month.title()}\"]'))) \
								.click()
			y_selector.click()

			WebDriverWait(self.driver, self.wait) \
						.until(EC.visibility_of_element_located((By.XPATH, 
							f'//ul[@role="menu"]/li/a/span/span[text()=\"{year}\"]'))) \
								.click()
		else:
			raise Exception('something is wrong with your attempt to search...')

		if what == 'photos':

			try:
				WebDriverWait(self.driver, self.wait) \
					.until(EC.visibility_of_element_located((By.XPATH, '//a[text()="See all"]'))).click()
			except:
				raise Exception('can\'t click on See All!')

			try:
				WebDriverWait(self.driver, self.wait) \
					.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.uiScaledImageContainer')))
			except:
				raise Exception('display picture doesn\'t appear following See All!')

		return self

		# 	self.scroll_and_collect()

		# 	for p in self.posts:
		# 		self.posts[p].update(self.get_post_details(self.posts[p]['post_url']))

		# elif (type == 'videos'):

		# 	self.scroll_and_collect_video()

		# 	for i, p in enumerate(self.posts, 1):
		# 		if i%10 == 0:
		# 			break
		# 		self.posts[p].update(self.get_post_details(self.posts[p]['post_url']))
		# 		self.posts[p].update(self.get_mob_post(self.posts[p]['post_url']))

	def save(self):

		json.dump(self.posts, open(f'{self.post_dir}/posts.json','w'))

		return self

	def get_content(self, id, url):

		"""
		download whatever the url points to; an example of a url we have:
		https://scontent-syd2-1.xx.fbcdn.net/v/t1.0-0/p526x296/12241297_994655900599825_5991089523523548804_n.jpg?

		https://video-syd2-1.xx.fbcdn.net/v/t42.1790-2/14099960_1136403553069791_825217156_n.mp4?_nc_cat=0&efg=eyJ2ZW5jb2RlX3RhZyI6InN2ZV9zZCJ9&oh=1d153c7c15f6de225227293d3d7926e2&oe=5B986C37
		"""
		print('downloading ', url)

		if not url:
			return None

		try:
			ext_ = re.search(r'(?<=\.)[a-z4]+(?=\?)',url).group(0)
		except:
			print('couldn\'t find extension!')
			return None

		if ext_ in self.extensions['video']:
			local_filename, headers = urllib.request.urlretrieve(url, os.path.join(self.video_dir, f'video_{id}.{ext_}'))
		elif ext_ in self.extensions['picture']:
			local_filename, headers = urllib.request.urlretrieve(url, os.path.join(self.picture_dir, f'picture_{id}.{ext_}'))

		return self



if __name__ == '__main__':

	fbd = Fbdown().login().search('timtamslam', what='photos', year='2017', month='june').scroll2()

	# for i, k in enumerate(fbd.posts, 1):
	# 	if i == 10:
	# 		break
	# 	fbd.get_content(k, fbd.posts[k].get('content_url', None))

	# fbd.save()


