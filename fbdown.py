from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import time
import json
import re

from collections import defaultdict

class Fbdown:

	def __init__(self):

		self.WAIT_SECS = 20

		options = webdriver.ChromeOptions()
		options.add_argument('disable-notifications')

		self.driver = webdriver.Chrome('webdriver/chromedriver', chrome_options=options)

		# self.driver = webdriver.Chrome('webdriver/chromedriver')

		self.login_url ='https://www.facebook.com'

		self.login_creds = json.load(open('credentials/facebook.json'))

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

		# top results first (it's normally 4 pictures)
		res = WebDriverWait(self.driver, self.WAIT_SECS) \
					.until(EC.visibility_of_element_located((By.ID, 'BrowseResultsContainer')))

		print('found container!')

		all_links = res.find_element_by_id('BrowseResultsContainer').find_elements_by_xpath('/descendant::a[@href]')

		print('found links: ', len(all_links))

		for n, _ in enumerate(all_links, 1):

			if not '?q=' in _.get_attribute('href'):
				continue

			print(f'link {n}...')
			print(_.get_attribute('href'))

			try:
				im = _.find_element_by_css_selector('img.scaledImageFitHeight')
				print('got image!', im)
			except:
				print('no image')
				
			time.sleep(1)



		return self







if __name__ == '__main__':

	fbd = Fbdown().login().search('timtamslam', month='march', year='2008')


