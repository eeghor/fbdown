from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from selenium.webdriver.chrome.options import DesiredCapabilities
from selenium.webdriver.common.proxy import Proxy, ProxyType

import time
import json
import re
import os
import copy 
import random

import itertools

import urllib.request

import arrow

from collections import defaultdict, Counter

import google.cloud.vision as gcv
from google.oauth2 import service_account
from google.protobuf.json_format import MessageToDict
import langcodes

class Fbdown:

	def __init__(self, wait=30, post_dir='posts', post_archive_dir='archive', video_dir='videos',
				 picture_dir='pictures', creds_dir='credentials'):

		self.video_dir = video_dir
		self.picture_dir = picture_dir
		self.post_dir = post_dir
		self.post_archive_dir = post_archive_dir
		self.creds_dir = creds_dir

		self.wait = wait

		# list of proxies to try
		self.proxies = []
		# list of proxies already tried
		self.used_proxies = []

		with open('proxies/proxies.txt') as f:
		    for line in f.readlines():   # ip: 190.12.55.210 port: 48994
		        ip = re.search(r'\b\d+\.\d+\.\d+\.\d+\b', line).group(0)
		        port = line.split()[-1]
		        self.proxies.append(ip + ':' + port)

		print(f'proxies: {len(self.proxies)}')

		self.today = arrow.utcnow().to('Australia/Sydney').format('YYYY-MM-DD')

		# some useful regex expressions to capture post IDs
		self.fbid_re = re.compile(r'(?<=p\.)\d+')
		self.fbidm_re = re.compile(r'(?<=fbid=)\d+')	  		# fbid=10154685918546439
		self.fbidt_re = re.compile(r'(?<=/)\d+(?=\/\?type)')    # /462352270791529/?type=
		self.vidid_re = re.compile(r'(?<=videos\/)\d+(?=\/)')   # videos/1672853176066872/

		self.reactions = 'like love haha wow sad angry'.split()
		self.extensions = {'video': ['mp4'], 'picture': ['jpg', 'png']}

		web_detection_params = gcv.types.WebDetectionParams(include_geo_results=True)
		image_context = gcv.types.ImageContext(web_detection_params=web_detection_params)

		self.face_feats = 'joy sorrow anger surprise under_exposed blurred headwear'.split()

		# credentials must be loaded as below, otherwise there will be an error
		client = gcv.ImageAnnotatorClient(credentials=service_account.Credentials \
								.from_service_account_file(f'{self.creds_dir}/ArnottsAU-7991416de13b.json'))

		if not os.path.exists(self.creds_dir):
			raise Exception('can\'t find the credentials directory!')

		for d in [self.post_dir, self.post_archive_dir, self.video_dir, self.picture_dir]:
			if not os.path.exists(d):
				os.mkdir(d)
		try:
			_ = json.load(open(os.path.join(self.post_dir, 'posts.json')))

			self.posts = {post_id: _[post_id] for post_id in _ if _[post_id].get('file', None) and _[post_id].get('content_url', None)}

			print(f'found {len(self.posts)} complete posts...')
		except:
			self.posts = defaultdict(lambda: defaultdict())
			print('collecting a new JSON with posts...')

		self.new_posts = defaultdict(lambda: defaultdict(lambda: defaultdict()))

	def start_browser(self, url='https://www.iplocation.net', proxy=False):

		# first set up some options
		options = webdriver.ChromeOptions()
		options.add_argument('--disable-notifications')
		options.add_argument('--ignore-certificate-errors')
		options.add_argument('--ignore-ssl-errors')
		# options.add_argument('headless')

		if proxy:

			while 1:

				print(f'proxies left to try: {len(self.proxies)}')

				if len(self.proxies) == 0:
					break

				capabilities = webdriver.DesiredCapabilities.CHROME
	
				prx = Proxy()   # contains information about proxy type and necessary proxy settings
		
				prx.proxy_type = ProxyType.MANUAL   # manual proxy settings
	
				# pick a random proxy
				p = self.proxies.pop(random.randint(0, len(self.proxies) - 1))

				print(f'testing proxy {p}...')

				# options.add_argument(f'--proxy-server={p}')

				# add this proxy to the list of used ones
				self.used_proxies.append(p)
	
				prx.http_proxy = prx.socks_proxy = prx.ssl_proxy = p
			
				prx.add_to_capabilities(capabilities)
	
				self.driver = webdriver.Chrome('webdriver/chromedriver', 
												chrome_options=options, desired_capabilities=capabilities)
				try:
					self.driver.get(url)
					new_ip = WebDriverWait(self.driver, 5) \
								.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '#wrapper > section > div > div > div.col.col_8_of_12 > div:nth-child(8) > div:nth-child(2) > p > span:nth-child(1)'))).text.strip()

					print(f'response: {new_ip.strip().lower()}. proxy works!')
					self.driver.close()
					break

				except:
					print(f'doesn\'t work')
		else:

			self.driver = webdriver.Chrome('webdriver/chromedriver', chrome_options=options)

		return self

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
			# becomes clickable; sometimes it's Events so try that one too
			try:
				WebDriverWait(self.driver, self.wait).until(EC.element_to_be_clickable((By.XPATH, f'//a[@data-testid="left_nav_item_Events"]')))
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

	def _get_url(self, url, n=2):

		attempt_ = 0

		while attempt_ < n:
			try:
				self.driver.get(url_)
				break
			except:
				print(f'couldn\'t get URL {url_}, refreshing page...')
				self.driver.refresh()
				attempt_ += 1

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

		heights_.append(self.driver.execute_script("return document.body.scrollHeight"))

		for n, blc_id in enumerate(self.block_generator()):
			
			print(f'block ID: {blc_id}')

			try:
				blc = WebDriverWait(self.driver, self.wait) \
										.until(EC.visibility_of_element_located((By.ID, blc_id)))
			except:
				print(f'can\'t find block {blc_id}! trying next one...')
				continue

			time.sleep(random.randint(2,8))
	
			# collect urls from this block
			try:
				ch_ = self.driver.find_elements_by_css_selector(f'#{blc_id} div:not([style])>a[href*="photo"][rel="theater"]')
			except:
				try:
					ch_ = self.driver.find_elements_by_css_selector(f'#{blc_id} div[role="VIDEOS"]>div>div>a[aria-label*="Video"]')
				except:
					print (f'no photos or videos! moving to next block...')
					continue
			
			urls_ = [_.get_attribute('href') for _ in ch_]

			duplicate_urls = {url: count for url, count in Counter(urls_).items() if count > 1}

			if duplicate_urls:
				print(f'found {len(duplicate_urls)} duplicate urls!')
			else:
				pass

			refs_ |= set(urls_)

			self._scroll_and_wait(n=1, s=6)
			
			heights_.append(self.driver.execute_script("return document.body.scrollHeight"))

			if (heights_[-3:].count(heights_[-1]) == 3):
				print(f'done scrolling...')
				break

			if n > 3:
				break
	
		# parse collected urls to extract post IDs
		for post_url in list(refs_):
			post_id = self._get_post_id(post_url)
			if post_id not in self.posts:
				# if we started from an empty self.new_posts, if should become {POSTID: {'post_url'}: 'URL1'}, ...}
				self.new_posts[post_id]['post_url'] = post_url

		print(f'found {len(self.new_posts)} posts not yet collected...')

		return self

	def _get_metrics(self, post_url_list):
		"""
		return {'post_url': {'metrics': {'date': {'likes': 3, 'wows': 2}}}}
		"""

		if not post_url_list:
			print('post url list is empty!')
			return None

		ms = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict())))

		for url_ in post_url_list:

			time.sleep(random.randint(2,8))

			nrefr = 0

			while nrefr < 3:
				try:
					self.driver.get(url_)
					break
				except:
					print(f'couldn\'t get URL {url_}, refreshing page...')
					self.driver.refresh()
					nrefr += 1
					time.sleep(4)

			# get comments, shares and reactions
			for _ in self.driver.find_elements_by_xpath('//a[@role="button"][@aria-live="polite"]'):
	
				# search for comments or shares, they may sit in text
				tx_ = _.text.lower()
	
				if tx_:
					for m in ['comments', 'shares']:
						try:
							ms[url_]['metrics'][self.today][m] = int(re.search(r'\d+\s+(?=' + f'{m})', tx_).group(0))
						except:
							pass

			for _ in self.driver.find_elements_by_xpath('//a[@role="button"][@aria-label]'):
				
				try:
					aria_tx_ = _.get_attribute('aria-label').lower().strip()
					
					for reaction_ in self.reactions:

						m_line = re.search(r'\d+\s+(?=' + f'{reaction_})', aria_tx_)

						if m_line:
							ms[url_]['metrics'][self.today][reaction_ + 's'] = int(m_line.group(0))
				except:
					continue

		return ms
	

	def get_post_details(self):

		"""
		given a url to the post page, go there and pick up some post details, such as all metrics and date posted;
		return these as a dictionary
		"""

		dict_ = copy.copy(self.new_posts)

		for i, post_id_ in enumerate(self.new_posts, 1):

			print(f'processing post {i}...')

			time.sleep(random.randint(2,8))

			# dictionary to collect post info; attach it to the post ID key
			this_post = defaultdict(lambda: defaultdict(lambda: defaultdict()))

			url_ = self.new_posts[post_id_]['post_url']

			if url_:
				self._get_url(url_)
			else:
				print('no post url available! skipping..')
				continue

			# get when posted
			try:
				this_post['posted'] = arrow.get(WebDriverWait(self.driver, self.wait) \
									.until(EC.visibility_of_element_located((By.XPATH, '//abbr[@title and @data-utime]'))) \
										.get_attribute('data-utime')) \
										.format('YYYY-MM-DD')
			except:
				# if a post has no timestamp, it's useless
				print('found a post without a timestamp! skipping..')
				continue

			# poster's url
			try:
				this_post['poster_url'] = WebDriverWait(self.driver, self.wait) \
						.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#fbPhotoSnowliftAuthorName>a[data-hovercard]'))).get_attribute('href').split('?')[0]
			except:
				print('no poster url..')

			# find content url, first for pictures
			try:
				this_post['content_url'] = WebDriverWait(self.driver, self.wait) \
												.until(EC.element_to_be_clickable((By.XPATH, '//img[@class="spotlight"][@alt][@src]'))) \
												.get_attribute('src')
			except:
				print('no content url for image. now searching for special content urls..')
				try:
					# need to visit the mobile version of the post
					rul_mob_ = dict_[post_id_]['post_url'].replace('www', 'm')
					print('loading mobile version of this page...')
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
			
			if this_post:
				dict_[post_id_] = this_post

		self.new_posts = dict_

		return self

	def update_metrics(self):

		print('updating new post metrics...')
		post_urls = [url for url in {self.new_posts[post_id].get('post_url', None) for post_id in self.new_posts} if url]
		print(f'total post urls: {len(post_urls)}')

		if not post_urls:
			raise Exception('no post urls in new posts!!')

		new_posts_metrics = self._get_metrics(post_urls)

		print(new_posts_metrics)
		
		for post_url in new_posts_metrics:
			for post_id in self.new_posts:
				if self.new_posts[post_id]['post_url'] == post_url:
					self.new_posts[post_id]['metrics'].update(new_posts_metrics[post_url]['metrics'])

		return self

	def get_poster(self):

		"""
		get poster's category if any; assume that you are on the post page
		"""

		if not self.new_posts:
			return self

		categs = defaultdict(lambda: defaultdict())

		# since there may be multiple posts by the same poster
		# we are looking at the unique poster_urls only

		unique_posters = list({poster_url for poster_url in {self.new_posts[p].get('poster_url', None) 
								for p in self.new_posts} if poster_url})

		print(f'unique posters: {len(unique_posters)}')

		for i, url_ in enumerate(unique_posters, 1):

			print(f'poster {i}/{len(unique_posters)}...')

			time.sleep(random.randint(3,15))

			nrefr = 0

			while nrefr < 3:
				try:
					self.driver.get(url_)
					break
				except:
					print(f'couldn\'t get URL {url_}, refreshing page...')
					self.driver.refresh()
					nrefr += 1

			# try to shut down the annoying popup
			try:
				WebDriverWait(self.driver, 6) \
							.until(EC.element_to_be_clickable((By.XPATH, '//a[@aria-label="Press Esc to close"]'))) \
								.click()
			except:
				pass

			about_ = intro_ = None

			try:
				about_ = WebDriverWait(self.driver, 6) \
								.until(EC.element_to_be_clickable((By.XPATH, '//div[@data-key="tab_about"]'))) 
			except:
				pass

			try:
				intro_ = WebDriverWait(self.driver, 6) \
								.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div#intro_container_id')))
			except:
				pass

			if about_:    # it's a business
				try:
					about_.click()
					categs[url_]['poster_category'] = ' - '.join([w.strip().lower() for w in re.split(r'[^\w\s]', 
														WebDriverWait(self.driver, self.wait) \
													.until(EC.element_to_be_clickable((By.XPATH, 
														'//u[text()="categories"]/../../following-sibling::div[@class]'))).text)])
				except:
					categs[url_]['poster_category'] = 'business'

			elif intro_:    # it's a person

				categs[url_]['poster_category'] = 'private'
				for line in intro_.text.strip().split('\n'):
					if 'lives in' in line.lower():
						categs[url_]['lives_in'] = line.lower()

		for p_url in categs:
			for p_id in self.new_posts:
				if self.new_posts[p_id]['poster_url'] == p_url:
					self.new_posts[p_id].update(categs[p_url])

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
				print('couldn\'t find anything...')
				return self

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

		# if not self.new_posts:
		# 	print('nothing to save')
		# 	return self

		json.dump({**self.posts, **self.new_posts}, open(f'{self.post_dir}/posts.json','w'))

		# if self.posts:
		# 	json.dump(self.posts, open(f'{self.post_archive_dir}/posts_{arrow.get(self.today).format("YYYYMMDD")}.json','w'))

		return self

	def get_content(self):

		"""
		download photos or videos
		"""

		if not self.new_posts:
			print('no new posts, nothing to download...')
			return self

		for _ in self.new_posts:

			url_ = self.new_posts[_]['content_url']
			
			if not url_:
				print('no content url found, moving on to next post...')
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
				print(f'downloading picture to {p}...', end='')
				local_filename, headers = urllib.request.urlretrieve(url_, p)
				urllib.request.urlcleanup()
				self.new_posts[_]['file'] = p
				print('ok')

		return self

	def annotate(self):
		"""
		using Google Vision API, annotate a photo
		"""
		f = open('pictures/picture_582887468579563.jpg', 'rb').read()

		r = MessageToDict(client.annotate_image({'image': 
								 {'content': f}, 'image_context': image_context}), 
										preserving_proto_field_name = True)
		annots = defaultdict(lambda: defaultdict())

		"""
		faces

		create a dictionary like this: {'faces': {'count': 2, 'face_1': {joy: very_unlikely, sorrow: very_unlikely, 
																anger: very_unlikely}}}
		"""

		def _count(what):

			try:
				return int(bool(r.get(f'{what}_annotations', None)))
			except:
				print(f'no {what}s')


		annots['faces']['count'] = _count('face')

		for i, face in enumerate(range(annots['faces']['count'])):
			
			this_face_ = []
			for feature in r['face_annotations'][i]:
				if '_likelihood' in feature:
					if r['face_annotations'][i][feature].lower() in 'likely very_likely'.split():
						this_face_.append(feature.replace('_likelihood',''))
	
			if this_face_:
				annots['faces']['face_' + str(i + 1)]

		"""
		logos

		"""	

		annots['logos']['count'] = _count('logo')

		if annots['logos']['count']:
			annots['logos']['descriptions'] = [r['logo_annotations'][i]['description'].lower() 
												for i, logo in enumerate(range(annots['logos']['count']))]


		"""
		labels

		these are various labels the API decided to produce, could be anything
		"""

		annots['labels']['count'] = _count('label')
		if annots['labels']['count']:
			annots['labels'] = {l['description']: round(l['score'], 3) for l in r['label_annotations']}

		"""
		themes; likelihoods can be one of the following:

		LIKELIHOOD_UNSPECIFIED
		VERY_UNLIKELY
		UNLIKELY	
		POSSIBLE	
		LIKELY
		VERY_LIKELY	

		"""
		detected_themes = [theme for theme, likelihood in r['safe_search_annotation'].items() 
													if likelihood.lower() in 'likely very_likely'.split()] 

		if detected_themes:
			annots['restricted_themes'] = detected_themes

		"""
		colors

		"""

		def _get_closest_color(color):
	
			distance_to_color = []
	
			for k, v in webcolors.css3_hex_to_names.items():
		
				# going through something like this: {#f0f8ff: aliceblue, #faebd7: antiquewhite}
				r,g,b = webcolors.hex_to_rgb(k)  # this converts #f0f8ff to integer RGB values
			
				distance_to_color.append((v, (r - color[0])**2 + (g - color[1])**2 + (b - color[2])**2))
		
			return min(distance_to_color, key=lambda x: x[1])[0]

		clrs = defaultdict(lambda: defaultdict())

		for c in r['image_properties_annotation']['dominant_colors']['colors']:
			# create an RGB tuple and get the closest color from CCS3 palette
			color = _get_closest_color(tuple([int(c) for c in (c['color']['red'], c['color']['green'], c['color']['blue'])]))
			clrs[color]['pixel_fraction'] = round(c['pixel_fraction'], 3)
			clrs[color]['score'] = round(c['score'], 3)

		annots['colors'] = clrs

		"""
		full text annotation

		"""

		# note that detected languages look like [{'language_code': 'ceb', 'confidence': 1.0}]
		try:
			annots['languages'] = sorted([(l['language_code'], l['confidence']) 
				for p in r['full_text_annotation']['pages'] for l in p['property']['detected_languages']], 
				key=lambda x: x[1], reversed=True)
		except:
			pass

		"""
		web detection

		"""
		try:
			annots['web_entities'] = {e['description'].lower(): round(e['score'], 3) 
						for e in r['web_detection']['web_entities'] if 'description' in e}
		except:
			pass

		"""
		localized objects

		"""
		try:
			annots['objects'] = {o['name'].lower(): round(o['score'], 3) for o in r['localized_object_annotations']}
		except:
			pass

		return annots


if __name__ == '__main__':

	fbd = Fbdown().start_browser(proxy=True)
	# .login() \
	# 				.search('timtamslam', what='photos', year='2018') \
	# 				.get_post_ids() \
	# 				.get_post_details() \
	# 				.get_content() \
	# 				.update_metrics().save() 
