from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

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
		# options.add_argument('headless')

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
			print(f'found {len(self.posts)} posts...')
			self.to_download = [{p: self.posts[p]} for p in self.posts if not self.posts[p].get('file', None)]
			print(f'previously collected posts with missing files: {len(self.to_download)}')
		except:
			self.posts = defaultdict(lambda: defaultdict())
			print('collecting a new JSON with posts...')

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

	def get_post_ids(self):
		"""
		after the search results have been displayed, collect all post ids not yet available
		"""

		refs_ = set() 

		heights_ = []

		posts_per_block = []

		is_last_page = reached_max = False

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

			try:
				ch_ = self.driver.find_elements_by_css_selector(f'#{blc_id} div:not([style])>a[href*="photo"][rel="theater"]')
			except:
				try:
					ch_ = self.driver.find_elements_by_css_selector(f'#{blc_id} div[role="VIDEOS"]>div>div>a[aria-label*="Video"]')
				except:
					print (f'no photos or videos here! moving on...')
					continue
			
			posts_per_block.append(len(ch_))
	
			refs_ |= {_.get_attribute('href') for _ in ch_}

			self._scroll_and_wait(n=1)
			
			heights_.append(self.driver.execute_script("return document.body.scrollHeight"))
	
			is_last_page = (heights_[-3:].count(heights_[-1]) == 3)

			# reached_max = (len(refs_) >= max_res)
	
			# if reached_max:
			# 	print(f'collected {len(refs_)} posts, more than requested max {max_res}; last searched block id: {blc_id}')
			# 	break

			if is_last_page:
				print(f'apparently, nowhere to scroll. last 3 page heights: {", ".join([str(h) for h in heights_[-3:]])}')
				break
	
		# parse collected urls to extract post IDs; note we now have urls for all blocks
		print('filtering post ids...')

		print(f'expected posts: {sum(posts_per_block)}')

		for post_url in list(refs_):
			post_id = self._get_post_id(post_url)
			if post_id not in self.posts:
				self.new_posts[post_id]['post_url'] = post_url

		print(f'collected {len(self.new_posts)} new posts')

		return self

	def get_post_details(self):

		"""
		given a url to the post page, go there and pick up some post details, such as all metrics and date posted;
		return these as a dictionary
		"""

		dict_ = copy.copy(self.new_posts)

		for p in dict_:

			url_ = dict_[p]['post_url']

			self.driver.get(url_)

			# dictionary to collect post info; attach it to the post ID key
			this_post = defaultdict(lambda: defaultdict(lambda: defaultdict()))

			# get when posted
			try:
				this_post['posted'] = arrow.get(WebDriverWait(self.driver, self.wait) \
									.until(EC.visibility_of_element_located((By.XPATH, '//abbr[@title and @data-utime]'))) \
										.get_attribute('data-utime')) \
										.format('YYYY-MM-DD')
			except:
				# if a post has no timestamp, it's useless
				print('WARNING: found a post without a timestamp! skipping..')
				continue

			# get comments, shares and reactions
			for _ in self.driver.find_elements_by_xpath('//a[@role="button"][@data-hover="tooltip"]'):
	
				# search for comments or shares, they may sit in text
				tx_ = _.text.lower()
	
				if tx_:
					for m in ['comments', 'shares']:
						try:
							this_post['metrics'][self.today][m] = int(re.search(r'\d+\s+(?=' + f'{m})', tx_).group(0))
						except:
							pass
			for _ in self.driver.find_elements_by_xpath('//a[@role="button"][@aria-label]'):
				
				try:
					aria_tx_ = _.get_attribute('aria-label').lower().strip()
					
					for m in self.reactions:
						m_line = re.search(r'\d+\s+(?=' + f'{m})', aria_tx_)
						if m_line:
							this_post['metrics'][self.today][m + 's'] = int(m_line.group(0))
				except:
					continue

			# poster's url
			try:

				this_post['poster_url'] = WebDriverWait(self.driver, self.wait) \
						.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#fbPhotoSnowliftAuthorName>a[data-hovercard]'))).get_attribute('href')
			except:
				print('no poster url..')

			# find content url, first for pictures
			try:

				this_post['content_url'] = WebDriverWait(self.driver, self.wait) \
												.until(EC.element_to_be_clickable((By.XPATH, '//img[@class="spotlight"][@alt][@src]'))) \
												.get_attribute('src')
			except:
				print('now searching for video or special image content url..')
				try:
					# need to visit the mobile version of the post
					rul_mob_ = dict_[p]['post_url'].replace('www', 'm')

					self.driver.get(rul_mob_)

					try:
						e = self.driver.find_element_by_xpath('//div[@data-sigil="inlineVideo"]')
					except:
						try:
							e = self.driver.find_element_by_xpath('//*[@data-sigil="photo-image"]')
						except:
							print(f'can\'t find content url at {rul_mob_}!')

					try:
						# this data-store looks like a dictionary but it's a string
						this_post['content_url'] = json.loads(e.get_attribute('data-store'))['src']
					except:
						try:
							this_post['content_url'] = json.loads(e.get_attribute('data-store'))['imgsrc']
						except:
							pass
				except:
					continue

			dict_[p].update(this_post)

		self.new_posts = dict_

		return self

	def get_poster(self):

		"""
		get poster's category if any; assume that you are on the post page
		"""
		
		# self.driver.find_elemenet_by_tag_name('body').send_keys(Keys.ESC)

		ct = None

		try:
			WebDriverWait(self.driver, self.wait) \
						.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#fbPhotoSnowliftAuthorName>a[data-hovercard]'))).click()
		except:
			print('couldn\'t click on poster\'s name!')
			return ct

		try:
			WebDriverWait(self.driver, self.wait) \
						.until(EC.element_to_be_clickable((By.XPATH, '//div[@data-key="tab_about"]'))) \
							.click()
		except:
			# this is not a business
			return ct

		try:
			ct = ' - '.join([w.strip().lower() for w in re.split(r'[^\w\s]', 
										WebDriverWait(self.driver, self.wait) \
										.until(EC.element_to_be_clickable((By.XPATH, '//u[text()="categories"]/../../following-sibling::div[@class]'))).text)])
		except:
			print('couldn\'t find categories on poster\'s page!')	

		return ct


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

		json.dump(self.new_posts, open(f'{self.post_dir}/new_posts.json','w'))

		json.dump({**self.posts, **self.new_posts}, open(f'{self.post_dir}/posts.json','w'))

		if self.posts:
			json.dump(self.posts, open(f'{self.post_archive_dir}/posts_{arrow.get(self.today).format("YYYYMMDD")}.json','w'))

		return self

	def get_content(self):

		"""
		download photos or videos
		"""

		for _ in self.new_posts:

			url_ = self.new_posts[_]['content_url']

			if not url_:
				print(f'missing content url for post id {_}! skipping download...')
				continue

			try:
				ext_ = re.search(r'(?<=\.)[a-z4]+(?=\?)', url_).group(0)
			except:
				print(f'couldn\'t find extension in {url_}!')
				continue

			if ext_ in self.extensions['video']:
				p = os.path.join(self.video_dir, f'video_{_}.{ext_}')
				print(f'downloading video to {p}...', end='')
				local_filename, headers = urllib.request.urlretrieve(url_, p)
				urllib.request.urlcleanup()
				self.new_posts[_]['file'] = p
				print('ok')
			elif ext_ in self.extensions['picture']:
				p = os.path.join(self.picture_dir, f'picture_{_}.{ext_}')
				print(f'downloading video to {p}...', end='')
				local_filename, headers = urllib.request.urlretrieve(url_, p)
				urllib.request.urlcleanup()
				self.new_posts[_]['file'] = p
				print('ok')

		return self

if __name__ == '__main__':

	fbd = Fbdown().login() \
					.search('timtamslam', what='photos', year='2018') \
					.get_post_ids() \
					.get_post_details() \
					.get_content().save() 




