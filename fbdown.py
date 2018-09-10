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

		login_button = WebDriverWait(self.driver, self.WAIT_SECS) \
							.until(EC.element_to_be_clickable((By.ID, 'loginbutton'))).click()
		time.sleep(2)

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

		# filter search results
		date_posted = WebDriverWait(self.driver, self.WAIT_SECS) \
					.until(EC.visibility_of_element_located((By.XPATH, '//h4[text()="DATE POSTED"]')))

		print('found date posted!')

		as_ = date_posted.find_elements_by_xpath('../a[@role="radio"]')

		if year and (not month):
			# find and click the right year option
			try:
				[a for a in as_ if year == a.text.strip()].pop().click()
			except:
				print(f'photos for {year} are unavailable!')

		elif year and month:

			# there's also an option to choose a custom month + year
			choosadate = date_posted.find_elements_by_xpath('../div[@role="radio"]')


		e_ = WebDriverWait(self.driver, self.WAIT_SECS) \
						.until(EC.visibility_of_element_located((By.XPATH, '//div[text()="Public photos"]')))
	

		see_all = WebDriverWait(self.driver, self.WAIT_SECS) \
					.until(EC.visibility_of_element_located((By.XPATH, '//a[text()="See all"]')))

		print('found see all!')

		return self







if __name__ == '__main__':

	fbd = Fbdown().login().search('timtamslam', year='2018')


