import logging
import os
from enum import Enum, auto
import requests

import garth


from .garmin_url_dict import GARMIN_URL_DICT

logger = logging.getLogger(__name__)


class GarminClient:
  def __init__(self, email, password, auth_domain, newest_num):
        self.auth_domain = auth_domain
        self.email = email
        self.password = password
        self.garthClient = garth
        # token 持久化目录，用于缓存登录状态避免重复触发 MFA
        self._token_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'db', 'garth_tokens'
        )
        os.makedirs(self._token_dir, exist_ok=True)
        # 默认超时 10 秒太短，佳明中国区 API 有时响应较慢，改为 30 秒
        self.garthClient.client.timeout = 30
        self.newestNum = int(newest_num)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36",
            "origin": GARMIN_URL_DICT.get("SSO_URL_ORIGIN"),
            "nk": "NT"
        }
  
  ## 登录装饰器
  def login(func):    
    def ware(self, *args, **kwargs):    
      import json
      # 先尝试从本地 token 文件加载
      token_path = os.path.join(self._token_dir, 'garth_tokens.json')
      if os.path.exists(token_path):
          try:
              with open(token_path, 'r') as f:
                  import json
                  data = json.load(f)
                  self.garthClient.loads(json.dumps(data))
          except Exception:
              pass
      
      try:
         garth.client.username
      except Exception:
        logger.warning("Garmin is not logging in or the token has expired.")
        if self.auth_domain and str(self.auth_domain).upper() == "CN":
          self.garthClient.configure(domain="garmin.cn")
        self.garthClient.login(self.email, self.password)
        
        # del self.garthClient.sess.headers['User-Agent']
        del self.garthClient.client.sess.headers['User-Agent']
        
        # 登录成功，将 token dump 到本地文件
        try:
            token_data = json.loads(self.garthClient.dumps())
            with open(token_path, 'w') as f:
                json.dump(token_data, f)
        except Exception:
            pass

      return func(self, *args, **kwargs)
    return ware
  
  @login 
  def download(self, path, **kwargs):
     return self.garthClient.download(path, **kwargs)
  
  @login 
  def connectapi(self, path, **kwargs):
      return self.garthClient.connectapi(path, **kwargs)
     

  ## 获取运动
  def getActivities(self, start:int, limit:int):
     
     params = {"start": str(start), "limit": str(limit)}
     activities =  self.connectapi(path=GARMIN_URL_DICT["garmin_connect_activities"], params=params)
     return activities;

  ## 获取所有运动
  def getAllActivities(self): 
    all_activities = []
    start = 0
    limit = 100
    while(True):
      activities = self.getActivities(start=start, limit=limit)
      if len(activities) > 0:
         all_activities.extend(activities)
         # 如果设定了 newestNum 且已拉够数，提前结束
         if self.newestNum > 0 and len(all_activities) >= self.newestNum:
             return all_activities[:self.newestNum]
      else:
         return all_activities
      start += limit

  ## 下载原始格式的运动
  def downloadFitActivity(self, activity):
    download_fit_activity_url_prefix = GARMIN_URL_DICT["garmin_connect_fit_download"]
    download_fit_activity_url = f"{download_fit_activity_url_prefix}/{activity}"
    response = self.download(download_fit_activity_url)
    return response

  @login  
  def upload_activity(self, activity_path: str):
    """Upload activity in fit format from file."""
    # This code is borrowed from python-garminconnect-enhanced ;-)
    file_base_name = os.path.basename(activity_path)
    file_extension = file_base_name.split(".")[-1]
    allowed_file_extension = (
        file_extension.upper() in ActivityUploadFormat.__members__
    )

    if allowed_file_extension:
       try:
        with open(activity_path, 'rb') as file:
          file_data = file.read()
          fields = {
              'file': (file_base_name, file_data, 'text/plain')
          }

          url_path = GARMIN_URL_DICT["garmin_connect_upload"]
          upload_url = f"https://connectapi.{self.garthClient.client.domain}{url_path}"
          self.headers['Authorization'] = str(self.garthClient.client.oauth2_token)
          response = requests.post(upload_url, headers=self.headers, files=fields, timeout=30)
          res_code = response.status_code
          result = response.json()
          upload_id = result.get("detailedImportResult", {}).get('uploadId')
          isDuplicateUpload = upload_id is None or upload_id == ''
          if res_code == 202 and not isDuplicateUpload:
              status = "SUCCESS"
          elif res_code == 409 and result.get("detailedImportResult", {}).get("failures", [])[0].get('messages', [])[0].get('content') == "Duplicate Activity.":
              status = "DUPLICATE_ACTIVITY"
              upload_id = None
          else:
              status = "UPLOAD_EXCEPTION"
              upload_id = None
          return (status, upload_id)
       except Exception as e:
            print(e)
            return ("UPLOAD_EXCEPTION", None)
    else:
        return ("UPLOAD_EXCEPTION", None)
  

class ActivityUploadFormat(Enum):
  FIT = auto()
  GPX = auto()
  TCX = auto()

class GarminNoLoginException(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, status):
        """Initialize."""
        super(GarminNoLoginException, self).__init__(status)
        self.status = status
