from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.touch_actions import TouchActions

import time
import json
import re
import os
import copy 

import itertools

import urllib.request

import arrow

from collections import defaultdict

class Fbdown:

	def __init__(self, wait=30, post_dir='posts', post_archive_dir='archive', video_dir='videos',
				 picture_dir='pictures', creds_dir='credentials'):

		self.wait = wait

		self.today = arrow.utcnow().to('Australia/Sydney').format('YYYY-MM-DD')

		options = webdriver.ChromeOptions()
		options.add_argument('disable-notifications')

		self.driver = webdriver.Chrome('webdriver/chromedriver', chrome_options=options)

		# some useful regex expressions to capture post IDs
		self.fbid_re = re.compile(r'(?<=p\.)\d+')
		self.fbidm_re = re.compile(r'(?<=fbid=)\d+')	  		# fbid=10154685918546439
		self.fbidt_re = re.compile(r'(?<=/)\d+(?=\/\?type)')    # /462352270791529/?type=
		self.vidid_re = re.compile(r'(?<=videos\/)\d+(?=\/)')   # videos/1672853176066872/

		self.reactions = 'like love haha wow sad angry'.split()
		self.extensions = {'video': ['mp4'], 'picture': ['jpg', 'png']}

		self.video_dir = video_dir
		self.picture_dir = picture_dir
		self.post_dir = post_dir
		self.post_archive_dir = post_archive_dir
		self.creds_dir = creds_dir

		if not os.path.exists(self.creds_dir):
			self.driver.close()
			raise Exception('can\'t find the credentials directory!')

		for d in [self.post_dir, self.post_archive_dir, self.video_dir, self.picture_dir]:
			if not os.path.exists(d):
				os.mkdir(d)
		try:
			self.posts = json.load(open(os.path.join(self.post_dir, 'posts.json')))
			print(f'found a post collection with {len(self.posts)} posts...')
		except:
			self.posts = defaultdict(lambda: defaultdict())
			print('starting a new post collection...')

		self.new_posts = defaultdict(lambda: defaultdict(lambda: defaultdict()))

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
							.until(EC.element_to_be_clickable((By.XPATH, '[//button[@name="login"]]')))
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

	def block_generator(self, i=-1):
		"""
		generator to produce block IDs
		"""
		while True:

			i += 1    # so that i starts from 0

			if i == 0:
				yield WebDriverWait(self.driver, self.wait) \
									.until(EC.presence_of_element_located((By.ID, 
										'BrowseResultsContainer'))) \
									.get_attribute('id')
			elif i == 1:
				yield WebDriverWait(self.driver, self.wait) \
									.until(EC.presence_of_element_located((By.XPATH, 
										'//div[@id="BrowseResultsContainer"]/following-sibling::div[@id]'))) \
									.get_attribute('id')
			elif i > 1:
				yield f'fbBrowseScrollingPagerContainer{i-2}'

	def _scroll_and_wait(self, n=1, s=3):
		"""
		do full page scroll n times, wait s seconds between scrolls
		"""
		for _ in range(n):

			self.driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight);")
			time.sleep(s)

	def _get_post_id(self, url):

		post_id = None

		try:
			post_id = self.fbid_re.search(url).group(0)
		except:
			try:
				post_id = self.fbidm_re.search(url).group(0)
			except:
				try:
					post_id = self.fbidt_re.search(url).group(0)
				except:
					try:
						post_id = self.vidid_re.search(url).group(0)
					except:
						pass

		if not post_id:
			print(f'no id in {url}!')

		return post_id

	def get_post_ids(self, what='photos', max_res=12):
		"""
		after the search results have been displayed, collect all post ids not yet available
		"""
		if what not in 'photos videos'.split():
			raise ValueError('get_post_ids needs parameter *what* to be either *photos* or *videos*!')

		refs_ = []  
		ids_ = []

		heights_ = []

		end_results = is_last_page = reached_max = still_loading = False

		hight_ = self.driver.execute_script("return document.body.scrollHeight")
		heights_.append(hight_)

		for n, blc_id in enumerate(self.block_generator()):
			
			print(f'block ID: {blc_id}')

			try:
				blc = WebDriverWait(self.driver, self.wait) \
										.until(EC.visibility_of_element_located((By.ID, blc_id)))
			except:
				print(f'can\'t find block {blc_id}!')
				continue
	
			# collect urls from this block

			if what == 'photos':
				ch_ = self.driver.find_elements_by_css_selector(f'#{blc_id} div:not([style])>a[href*="photo"][rel="theater"]')
			elif what == 'videos':
				ch_ = self.driver.find_elements_by_css_selector(f'#{blc_id} div[role="VIDEOS"]>div>div>a[aria-label*="Video"]')

			if not ch_:
				print (f'this block appears to have no children! moving on to the next one')
				continue
	
			refs_.extend([_.get_attribute('href') for _ in ch_])
			
			ids_.extend([self._get_post_id(r) for r in refs_])

			self._scroll_and_wait(n=1)
			
			heights_.append(self.driver.execute_script("return document.body.scrollHeight"))
	
			is_last_page = (heights_[-3:].count(heights_[-1]) == 3)

			reached_max = (len(refs_) >= max_res)
	
			if reached_max:
				print(f'collected {len(refs_)} posts, more than requested max {max_res}; last searched block id: {blc_id}')
				break

			if is_last_page:
				print(f'apparently, nowhere to scroll. last 3 page heights: {", ".join(heights_[-3:])}')
				break
	
		# prs collected urls to extract post IDs
		print('filtering post ids...')

		for post_url, post_id in zip(refs_, ids_):
			if post_id not in self.posts:
				self.new_posts[post_id] = {'post_url': post_url}

		print(f'collected {len(self.new_posts)} new posts')

		return self

	def get_post_details(self):

		"""
		given a url to the post page, go there and pick up some post details, such as all metrics and date posted;
		return these as a dictionary
		"""

		dict_ = copy.copy(self.new_posts)

		for p in self.new_posts:

			self.driver.get(self.new_posts[p]['post_url'])

			# dictionary to collect post info; attach it to the post ID key
			this_post = defaultdict(lambda: defaultdict(lambda: defaultdict()))

			# get when posted
			try:
				this_post['when_posted'] = arrow.get(WebDriverWait(self.driver, self.wait) \
									.until(EC.visibility_of_element_located((By.XPATH, '//abbr[@title and @data-utime]'))) \
										.get_attribute('data-utime')) \
										.format('YYYY-MM-DD')
			except:
				# if a post has no timestamp, it's useless
				print('WARNING: found a post without a timestamp! skipping..')
				continue

			# get comments, shares and reactions
			for _ in self.driver.find_elements_by_xpath('//a[@role="button"]'):
	
				# search for comments or shares, they may sit in text
				tx_ = _.text.lower()
	
				if tx_:
					for m in ['comments', 'shares']:
						m_line = re.search(r'\d+\s+(?=' + f'{m})', tx_)
						if m_line:
							this_post['metrics'][self.today][m] = int(m_line.group(0))
	
				try:
					aria_tx_ = _.get_attribute('aria-label').lower().strip()
					
					for m in self.reactions:
						m_line = re.search(r'\d+\s+(?=' + f'{m})', aria_tx_)
						if m_line:
							this_post['metrics'][self.today][m + 's'] = int(m_line.group(0))
				except:
					continue

			# find content url, first for pictures
			try:
				this_post['content_url'] = self.driver.find_element_by_class_name('spotlight').get_attribute('src')
			except:
				try:
	
					# ActionChains(self.driver) \
					# 		.move_to_element(self.driver.find_element_by_xpath('//video[@src]')) \
					# 		.context_click() \
					# 		.perform()

					# need to visit the mobile version of the post
					self.driver.get(dict_[p]['post_url'].replace('www', 'm'))

					try:
						e = self.driver.find_element_by_xpath('//div[@data-sigil="inlineVideo"]')
					except:
						try:
							e = self.driver.find_element_by_xpath('//div[@data-sigil="photo-image"]')
						except:
							print('can\'t find content url!')

					try:
						# this data-store looks like a dictionary but it's a string
						this_post['content_url'] = json.loads(e.get_attribute('data-store'))['src']
					except:
						pass
				except:
					continue

			dict_[p] = this_post

		self.new_posts = dict_

		return self

	def search(self, tag, what='photos', month=None, year=None):
		"""
		search by tag and then filter by date; for photos there's an option to select specific month and year, 
		but for videos you can pick the year only
		"""
		self.driver.get('https://www.facebook.com/')

		try:
			WebDriverWait(self.driver, self.wait) \
							.until(EC.element_to_be_clickable((By.XPATH, '//input[@placeholder="Search"]'))) \
								.send_keys(tag)
			time.sleep(2)
		except:
			raise Exception('couldn\'t find the search field up the top!')

		try:
			WebDriverWait(self.driver, self.wait) \
							.until(EC.element_to_be_clickable((By.XPATH, '//button[@type="submit"][@data-testid]'))) \
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

		time.sleep(5)

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

	def save(self):
		"""
		update posts with the new ones and save to s JSON
		"""
		json.dump({**self.posts, **self.new_posts}, open(f'{self.post_dir}/posts.json','w'))

		json.dump(self.posts, open(f'{self.post_archive_dir}/posts_{arrow.get(self.today).format("YYYYMMDD")}.json','w'))

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

	fbd = Fbdown().login().search('timtamslam', what='videos', year='2017') \
					.get_post_ids(max_res=15, what='videos') \
					.get_post_details().save() \
					.search('timtamslam', what='photos', year='2017') \
					.get_post_ids(max_res=15, what='photos') \
					.get_post_details().save()



