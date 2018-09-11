from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import time
import json
import re

import arrow

from collections import defaultdict

class Fbdown:

	def __init__(self):

		self.WAIT_SECS = 30

		options = webdriver.ChromeOptions()
		options.add_argument('disable-notifications')

		self.driver = webdriver.Chrome('webdriver/chromedriver', chrome_options=options)

		# self.driver = webdriver.Chrome('webdriver/chromedriver')

		self.login_url ='https://www.facebook.com'

		self.fbid_re = re.compile(r'(?<=p.)\d+')

		self.login_creds = json.load(open('credentials/facebook.json'))

		self.reactions = 'like love haha wow sad angry'.split()

		self.posts = defaultdict(lambda: defaultdict())

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

		return {post_id: {'post_url': post_url, 'content_url': content_url}}


	def scroll_and_collect(self, max_items=10):

		for block_xpath in ['//div[@id="BrowseResultsContainer"]/div/div/div/a[@href]',
								'//div[@data-testid="paginated_results_pagelet"]/div/div/div/div/a[@href]']:
			for _ in self.driver.find_elements_by_xpath(block_xpath):

				self.posts.update(self._get_post_info(_))

				# im = _.find_element_by_xpath('descendant::img')

				# post_url = _.get_attribute('href')
				# post_id = self.fbid_re.search(post_url).group(0)
				# content_url = im.get_attribute('src')

				# self.posts.append({'post_url': _.get_attribute('href'), 
				# 					'content_url': im.get_attribute('src')})

		# for _ in self.driver.find_elements_by_xpath('//div[@data-testid="paginated_results_pagelet"]/div/div/div/div/a[@href]'):

		# 	im = _.find_element_by_xpath('descendant::img')

		# 	self.posts.append({'post_url': _.get_attribute('href'), 
		# 							'content_url': im.get_attribute('src')})

		hight_ = self.driver.execute_script("return document.body.scrollHeight")

		c = 0

		while len(self.posts) <= max_items:

			self.driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight);")
			time.sleep(5)

			for _ in self.driver.find_elements_by_xpath(f'//div[@id="fbBrowseScrollingPagerContainer{c}"]/div/div/div/div/a[@href]'):

				self.posts.update(self._get_post_info(_))

				# im = _.find_element_by_xpath('descendant::img')
				# self.posts.append({'post_url': _.get_attribute('href'), 
				# 					'content_url': im.get_attribute('src')})

			print(f'collected urls so far: {len(self.posts)}')

			new_height = self.driver.execute_script("return document.body.scrollHeight")

			if new_height > hight_:
				hight_ = new_height
			else:
				print('reached the bottom of the page')
				break

			c += 1

		return self

	def get_post(self, post_url):

		self.driver.get(post_url)

		d = dict()

		try:

			d.update({'when_posted': arrow.get(WebDriverWait(self.driver, self.WAIT_SECS) \
								.until(EC.visibility_of_element_located((By.CLASS_NAME, 'timestampContent'))).text.strip(), 
									'D MMMM YYYY').to('Australia/Sydney').format('YYYY-MM-DD')})

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
					d.update({m+ 's': int(m_line.group(0))})

		return d

	def search(self, tag, month=None, year=None):

		search_field = WebDriverWait(self.driver, self.WAIT_SECS) \
							.until(EC.element_to_be_clickable((By.XPATH, '//input[@placeholder="Search"]'))) \
								.send_keys(tag)

		time.sleep(5)

		submit_button = WebDriverWait(self.driver, self.WAIT_SECS) \
							.until(EC.element_to_be_clickable((By.XPATH, '//button[@type="submit"]'))) \
								.click()

		time.sleep(2)

		tb_ = WebDriverWait(self.driver, self.WAIT_SECS) \
					.until(EC.element_to_be_clickable((By.XPATH, '//li[@data-edge="keywords_blended_photos"]/a[@href]'))).click()
		
		time.sleep(2)

		print('do we see Public Photos?')

		try:

			e_ = WebDriverWait(self.driver, self.WAIT_SECS) \
					.until(EC.visibility_of_element_located((By.XPATH, '//div[text()="Public photos"]')))

			# self.driver.find_element_by_xpath('//div[text()="Public photos"]')

			print('got it!')
			print(e_.text)

		except:

			print('no, still nothing')

		

		if year and (not month):
			# find and click the right year option

			date_posted = WebDriverWait(self.driver, self.WAIT_SECS) \
					.until(EC.visibility_of_element_located((By.XPATH, '//h4[text()="DATE POSTED"]')))

			as_ = date_posted.find_elements_by_xpath('../a[@role="radio"]')

			try:
				[a for a in as_ if year == a.text.strip()].pop().click()
			except:
				print(f'photos for {year} are unavailable!')

		elif year and month:

			self._choose_date(month=month, year=year)
	

		see_all = WebDriverWait(self.driver, self.WAIT_SECS) \
					.until(EC.visibility_of_element_located((By.XPATH, '//a[text()="See all"]')))

		print('found see all!')

		see_all.click()

		time.sleep(5)

		self.scroll_and_collect()

		for p in self.posts:
			self.posts[p].update(self.get_post(self.posts[p]['post_url']))
		
		json.dump(self.posts, open('posts.json','w'))

		return self


if __name__ == '__main__':

	fbd = Fbdown().login().search('timtamslam', month='march', year='2008')


