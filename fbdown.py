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

import urllib.request

import arrow

from collections import defaultdict

class Fbdown:

	def __init__(self):

		self.WAIT_SECS = 30

		options = webdriver.ChromeOptions()
		options.add_argument('disable-notifications')

		self.driver = webdriver.Chrome('webdriver/chromedriver', chrome_options=options)

		self.login_url ='https://www.facebook.com'

		self.fbid_re = re.compile(r'(?<=p.)\d+')

		self.login_creds = json.load(open('credentials/facebook.json'))

		self.reactions = 'like love haha wow sad angry'.split()

		self.posts = defaultdict(lambda: defaultdict())

		self.video_dir = 'videos'

		if not os.path.exists(self.video_dir):
			os.mkdir(self.video_dir)

		self.picture_dir = 'pictures'

		if not os.path.exists(self.picture_dir):
			os.mkdir(self.picture_dir)

	def login(self):

		print('logging in...')

		self.driver.get(self.login_url)

		self.driver.find_element_by_name("email").send_keys(self.login_creds['user'])
		self.driver.find_element_by_name("pass").send_keys(self.login_creds['password'])

		try:

			WebDriverWait(self.driver, self.WAIT_SECS) \
							.until(EC.element_to_be_clickable((By.ID, 'loginbutton'))).click()
		except:

			try:
				WebDriverWait(self.driver, self.WAIT_SECS) \
							.until(EC.element_to_be_clickable((By.XPATH, '[//button[@type="submit"]]'))).click()
			except:
				print('could not log in!')

		time.sleep(2)

		return self

	def _choose_date(self, month=None, year=None):
		"""
		pick photos posted during a specific month of year
		"""
		m_selected = y_selected = False

		while not (m_selected and y_selected):

			date_posted = WebDriverWait(self.driver, self.WAIT_SECS) \
					.until(EC.visibility_of_element_located((By.XPATH, '//h4[text()="DATE POSTED"]')))

			# there's also an option to choose a custom month + year
			try:
				date_posted.find_element_by_xpath('../div[@role="radio"]').click()
			except:
				pass

			m_selector, y_selector = self.driver.find_elements_by_xpath('//h4[text()="DATE POSTED"]/../descendant::a[@rel="toggle"]')

			if not m_selected:

				m_selector.click()

				WebDriverWait(self.driver, self.WAIT_SECS) \
						.until(EC.visibility_of_element_located((By.XPATH, f'//ul[@role="menu"]/li/a/span/span[text()=\"{month.title()}\"]'))).click()

				m_selected = True

			elif not y_selected:

				y_selector.click()

				WebDriverWait(self.driver, self.WAIT_SECS) \
						.until(EC.visibility_of_element_located((By.XPATH, f'//ul[@role="menu"]/li/a/span/span[text()=\"{year}\"]'))).click()

				y_selected = True


			else:

				print('some problem with the month/year selectors!')	

			WebDriverWait(self.driver, self.WAIT_SECS) \
					.until(EC.visibility_of_element_located((By.XPATH, '//div[text()="Public photos"]')))

		print(f'selected date: {month.title()}, {year}')

		return self	

	def _get_post_info(self, a):

		post_url = a.get_attribute('href')
		post_id = self.fbid_re.search(post_url).group(0)
		content_url = a.find_element_by_xpath('descendant::img').get_attribute('src')

		return {post_id: {'post_url': post_url, 'content_url': content_url, 'type': 'picture'}}

	def _get_video_post_info(self, dv):

		a = dv.find_element_by_xpath('descendant::a[@aria-label]')

		if 'Video' in a.get_attribute('aria-label'):

			post_url = a.get_attribute('href')
			post_id = re.search(r'(?<=videos\/)\d+(?=\/)', post_url).group(0)

		return {post_id: {'post_url': post_url, 'type': 'video/mp4'}}


	def scroll_and_collect(self, max_items=10):

		for block_xpath in ['//div[@id="BrowseResultsContainer"]/div/div/div/a[@href]',
								'//div[@data-testid="paginated_results_pagelet"]/div/div/div/div/a[@href]']:
			for _ in self.driver.find_elements_by_xpath(block_xpath):

				self.posts.update(self._get_post_info(_))

		hight_ = self.driver.execute_script("return document.body.scrollHeight")

		c = 0

		while len(self.posts) <= max_items:

			self.driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight);")
			time.sleep(5)

			for _ in self.driver.find_elements_by_xpath(f'//div[@id="fbBrowseScrollingPagerContainer{c}"]/div/div/div/div/a[@href]'):

				self.posts.update(self._get_post_info(_))

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

			all_divs = self.driver.find_elements_by_xpath('//div[@role="VIDEOS"]')

			print('have divs: ', len(all_divs))

			for i, _ in enumerate(all_divs, 1):
				self.posts.update(self._get_video_post_info(_))
				
		return self


	def get_post(self, post_url):

		self.driver.get(post_url)

		d = dict()

		try:

			d.update({'when_posted': arrow.get(WebDriverWait(self.driver, self.WAIT_SECS) \
								.until(EC.visibility_of_element_located((By.CLASS_NAME, 'timestampContent'))).text.strip(), 
									'D MMMM YYYY').to('Australia/Sydney').format('YYYY-MM-DD')})

		except:

			try:
				d.update({'when_posted': arrow.get(WebDriverWait(self.driver, self.WAIT_SECS) \
								.until(EC.visibility_of_element_located((By.CLASS_NAME, 'timestamp')).get_attribute('data-utime'))).format('YYYY-MM-DD')})

			except:
				pass

		for m in ['comments', 'shares']:

			for _ in self.driver.find_elements_by_xpath('//a[@role="button"]'):

				tx_ = _.text.lower()

				if not tx_:
					continue

				m_line = re.search(r'\d+\s+(?=' + f'{m})', tx_)

				if m_line:
					d.update({m: int(m_line.group(0))})

		for _ in self.driver.find_elements_by_xpath('//a[@role="button" and @aria-label]'):
			
			tx_ = _.get_attribute('aria-label').lower().strip()

			for m in self.reactions:

				m_line = re.search(r'\d+\s+(?=' + f'{m})', tx_)

				if m_line:
					d.update({m + 's': int(m_line.group(0))})

		# get the content url - for videos only
		try:

			ActionChains(self.driver) \
					.move_to_element(self.driver.find_element_by_xpath('//video[@src]')) \
					.context_click() \
					.perform()

			d.update({'content_url': self.driver.find_element_by_xpath('//span[@value]').get_attribute('value')})
			
		except:
			pass

		return d

	def get_mob_post(self, post_url):
		"""
		get direct video url 
		https://www.facebook.com/abccoffscoast/videos/2117273828315294/
		https://m.facebook.com
		"""
		new_url = post_url.replace('https://www', 'https://m')

		print('getting ', new_url)

		self.driver.get(new_url)

		_ = self.driver.find_element_by_xpath('//div[@data-sigil="inlineVideo"]')

		# this data-store looks like a dictionary but it's a string
		ds_ = json.loads(_.get_attribute('data-store'))

		url = ds_['src']

		return {'content_url': url}


	def search(self, tag, type='photos', month=None, year=None):

		search_field = WebDriverWait(self.driver, self.WAIT_SECS) \
							.until(EC.element_to_be_clickable((By.XPATH, '//input[@placeholder="Search"]'))) \
								.send_keys(tag)

		time.sleep(5)

		submit_button = WebDriverWait(self.driver, self.WAIT_SECS) \
							.until(EC.element_to_be_clickable((By.XPATH, '//button[@type="submit"]'))) \
								.click()

		time.sleep(2)

		tb_ = WebDriverWait(self.driver, self.WAIT_SECS) \
					.until(EC.element_to_be_clickable((By.XPATH, f'//li[@data-edge="keywords_blended_{type}"]/a[@href]'))).click()
		
		time.sleep(2)

		if type == 'photos':

			try:
	
				e_ = WebDriverWait(self.driver, self.WAIT_SECS) \
						.until(EC.visibility_of_element_located((By.XPATH, '//div[text()="Public photos"]')))
			except:
				pass

		

		if year and (not month):
			# find and click the right year option

			date_posted = WebDriverWait(self.driver, self.WAIT_SECS) \
					.until(EC.visibility_of_element_located((By.XPATH, '//h4[text()="DATE POSTED"]')))

			as_ = date_posted.find_elements_by_xpath('../a[@role="radio"]')

			try:
				[a for a in as_ if year == a.text.strip()].pop().click()
			except:
				print(f'{type} for {year} are unavailable!')

		elif year and month and (type == 'photos'):

			self._choose_date(month=month, year=year)

		else:
			print(f'date selected incorrectly for {type}')
			return None
	
		if (type == 'photos'):
			see_all = WebDriverWait(self.driver, self.WAIT_SECS) \
					.until(EC.visibility_of_element_located((By.XPATH, '//a[text()="See all"]')))

			print('found see all!')

			see_all.click()

			time.sleep(5)

			self.scroll_and_collect()

			for p in self.posts:
				self.posts[p].update(self.get_post(self.posts[p]['post_url']))

		elif (type == 'videos'):

			self.scroll_and_collect_video()

			for i, p in enumerate(self.posts, 1):
				if i%10 == 0:
					break
				self.posts[p].update(self.get_post(self.posts[p]['post_url']))
				self.posts[p].update(self.get_mob_post(self.posts[p]['post_url']))
		
		json.dump(self.posts, open('posts.json','w'))

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

		if ext_ == 'mp4':
			local_filename, headers = urllib.request.urlretrieve(url, os.path.join(self.video_dir, f'video_{id}.{ext_}'))
		elif ext_ in ['jpg', 'png']:
			local_filename, headers = urllib.request.urlretrieve(url, os.path.join(self.picture_dir, f'picture_{id}.{ext_}'))

		return self



if __name__ == '__main__':

	fbd = Fbdown().login().search('timtamslam', type='videos', year='2018')

	for i, k in enumerate(fbd.posts, 1):
		if i == 10:
			break
		fbd.get_content(k, fbd.posts[k].get('content_url', None))


