import base64
import time
import json
import logging
import traceback

import requests
from lxml import etree
from requests.exceptions import Timeout, ReadTimeout, ProxyError, ConnectionError


info_logger = logging.getLogger("info_log")
err_logger = logging.getLogger("err_log")
detail_logger = logging.getLogger("detail_log")


class PhoneRegisterCheck:
    """
    支付宝注册情况检验:
        1. 实例化PhoneRegisterCheck;
        2. 调用check方法;
    检验返回的状态码:
        0 : 号码已注册;
        1 : 号码未注册;
        -1 : 结果异常(验证码错误, 其它错误);
    """

    def __init__(self):
        """
            初始化session, 获取IP代理
        """
        self.session = requests.session()
        self.proxies = get_proxies()
        # self.proxies = None
        self.img_data = b''

    def get_captcha_code(self):
        """
        :return:  表单token & 验证码
        """

        result = {'_form_token': None, 'captcha_code': None, 'failReason': None}

        url = 'https://accounts.alipay.com/console/dispatch.htm?scene_code=resetQueryPwd&page_type=fullpage&site=1'
        try:
            resp = self.session.get(url, proxies=self.proxies, timeout=(6.1, 15))
            content = resp.content.decode(encoding='GBK')

            tree = etree.HTML(content)
            _form_token = tree.xpath('//input[@name="_form_token"]/@value')

            if _form_token:
                _form_token = _form_token[0]
                result['_form_token'] = _form_token
            else:
                result['failReason'] = '_form_token未找到'
                return result

            captcha_url = tree.xpath('//img[@alt="输入验证码"]/@src')
            if captcha_url:
                captcha_url = captcha_url[0]
            else:
                result['failReason'] = '验证码url未找到'
                return result

            img_data = self.session.get(captcha_url, proxies=self.proxies, timeout=(6.1, 15)).content
            self.img_data = img_data

            # 第三方验证码接口
            img_b64 = self.img_encoder(img_data)
            if not img_b64:
                result['failReason'] = '图片无法转换为base64'
                return result
            begin = time.time()
            captcha_code = crack_captcha(img_b64)
            print('本次验证码请求耗时: 【%.2fs】'% (time.time()-begin))

            # --*-- 手动输入验证码进行测试 --*--
            # from io import BytesIO
            # from PIL import Image
            # img_like = BytesIO(img_data)
            # img = Image.open(img_like)
            # img.show()
            # captcha_code = input('请输入验证码: ')
            # --*-- 手动输入验证码进行测试end --*--

            if not captcha_code:
                result['failReason'] = '验证码识别错误'
                return result
            result['captcha_code'] = captcha_code
            return result

        except ProxyError as e:
            print('IP代理错误', e)
        except ConnectionError as e:
            print('连接错误', e)
        except (Timeout, ReadTimeout) as e:
            print('请求超时', e)
        except Exception as e:
            print('其它错误', traceback.format_exc())

        result['failReason'] = '网络请求错误'
        return result

    def get_check_result(self, _form_token, captcha_code, phone):
        """
        :param _form_token:  表单token
        :param captcha_code:  验证码
        :param phone:   手机号码
        :return: check 结果
        """
        result = {'statusCode': None, 'registerStatus': None, 'failReason': None}

        url = 'https://accounts.alipay.com/console/querypwd/logonIdInputReset.htm?site=1&page_type=fullpage&scene_code=resetQueryPwd&return_url='

        data = {
            'ua': '084BqFYKOYNNcUuXukRErVNJIN+ErdLIZYCAw==|BaFEKYlxHLpCJ4Z9GLlII+s=|BKNGQfZ8SK8JOMgjU+Qbd8AlW5k5C/pcd5F6e7M=|A6dcLJs3D6IOYs5mA65WP5kyCK1QPZw3Xf9XM5NjXf1SN5Q7BfENYsI+BqBYNJQ7UvMNMMQ0X/gFbsk1D6IKMsRuCq9UT4B5FaI2|AqZWJugTY8c8TOgZad5hXLtSb48/GbEjV/JDLNwtVPEaG9M=|AaxJN4AU|AKxJN4AU|D6tTI+0GMtNuQqRXJJ42Cf9ZcIs2GaIKOsZ/Qq5JdowoW60LOd95SblfcpI+EPxFbp95SbMdLtVVbbEWOtpnaZkjGvscKMltDuhIYJBkCboDPsxgY4IyHu4aIMBlVbAYI9M8E+VJe4sdIth1TORfZoAsBMB8RaISHvxRL5Z9A8tf|DqhNSu8KZt8nQuUcbM8xW+Iaf9ghUfUMaM0oRekSfsc/U/ILCsI=|Da5LTPsQYMQ/UOkQYMc9UPRgYQ==|DK1IT/h7Cv5Ua7AYKdkyQuMYdM02W/YTfNAvSoIW|C6tOSf59DPhSbbYeL980RIp3GrpfMZVub9YvX+gDc9IqTup+fw==|CqhNSv1+D/tRbrUdLNw3R+MGbso7VJwI|CalMS/x/DvpQb7QcLd02Roh1GLhdM5dsbdQtXeoBcdEuS+h8fQ==|CKhNSv1+D/tRbrUdLNw3R4l0GblcMpZtbNUsXOsAcNAhS+t/fg==|F7RRVuFiE+dNcqkBMMArW/8BcdQxWPQFYak9|FrVQV+BjEuZMc6gAMcEqWvkHd9M2X/MDb6cz|FbZTVONgEeVPcKsDMsIpWfULe947Xv4AaaE1|FLZTVONgEeVPcKsDMsIpWfwZdNcpQ+56ew==|E7FUU+RnFuJId6wENcUuXvofctAsReJ2dw==|ErJXUOdkFeNCe40vEOpHfsksK419GaBbMJcDc9YzTfofctAsReh8fQ==|EbNWUeZlFOBKda4GN8csXPkccdMvReN3dg==|ELJXUOdkFeNCe40vEOpHfsksQfgAa8s0UJgM|H75bXOsAcNEtRP0Gbc0oRuEbcd1JSA==|Hr9aXeoBcdEpRfwHbMovQeAZdtdDQg==|Hb9aXeppGO5PdoAiHedKc8QhTfQPZsc6XpYC|HL1YX+gDc9IjTfQPZMgtQ+MSf9NHRg==|G7lcW+xvHuhJcIYkG+FMdcInSvMIYsU0WJAE|GrpfWO8EdLpAJIdiDapTUusSYtU+TukWeNUpKOA=|GbteWe5tHOpLcoQmGeNOd8AlSfALYcY2WpIG|GLpfWO8EdNA1W/gDZsZSUw==|J4Z/E6pTI4RhDK1VJYN/FK1RNI1zGqNbNpdyH6ZdNo9wAKRZKY9xAaVeLopyAqVdLYpzA6dXJ4F5Ca9WJoZjDaBFK4lsHb9aK4ZjDaxJOJxlFbJJOYF7C6xVJYFxcA==',
            '_form_token': _form_token,
            'logonId': phone,
            'picCheckCode': captcha_code
        }
        try:
            resp = self.session.post(url, proxies=self.proxies, data=data, timeout=(6.1, 15))
            content = resp.content.decode(encoding='GBK')
        except Exception as e:
            print(e)
            result['statusCode'] = -1
            result['failReason'] = '网络请求错误.'
            return result
        tree = etree.HTML(content)
        check = tree.xpath('//div[@class="ui-form-explain pt-5"]/text()')
        if check:
            check = check[0].strip()
            if check == '请输入正确的验证码':
                result['statusCode'] = -1
                result['failReason'] = '验证码识别错误'
                return result
            elif check == '该账户不存在，请重新输入':
                result['statusCode'] = 1
                result['registerStatus'] = '号码未注册'
                return result
            else:
                result['statusCode'] = -1
                result['failReason'] = '页面解析错误,未找到check标志'
                return result

        else:
            result['statusCode'] = 0
            result['registerStatus'] = '号码已注册'
            return result

    def check(self, phone, save_img=False):
        result = {'statusCode': None, 'registerStatus': None, 'failReason': None}

        captcha_result = self.get_captcha_code()
        _form_token = captcha_result.get('_form_token')
        captcha_code = captcha_result.get('captcha_code')
        fail_reason = captcha_result.get('failReason')

        if not _form_token or not captcha_code:
            result['statusCode'] = -1
            result['failReason'] = fail_reason
            return result

        result = self.get_check_result(_form_token, captcha_code, phone)

        # --*-- 验证码图片保存 --*--
        if save_img:
            import os
            import uuid
            u = uuid.uuid1()
            folder = os.path.dirname(os.path.abspath(__file__))
            if result.get('statusCode') != -1:
                file_name = str(captcha_code) + '_' + str(u) + '.png'
                file = os.path.join(folder, 'images', file_name)
            else:
                file_name = 'error_' + str(captcha_code) + '_' + str(u) + '.png'
                file = os.path.join(folder, 'images', 'error', file_name)
                print('error captcha ... ')
            with open(file, 'wb') as f:
                f.write(self.img_data)
        # --*-- 验证码图片保存end --*--

        return result

    @staticmethod
    def img_encoder(img_data):
        try:
            img_b64 = base64.encodebytes(img_data).decode()
            return img_b64
        except Exception as e:
            print(e)
            return None


def get_proxies():
    begin = time.time()
    # url = 'http://127.0.0.1:5020/ip/get/'
    url = 'http://192.168.30.248:8080/get/'
    try:
        count = 0
        while count < 5:
            content = requests.get(url, timeout=3.1).content
            info = json.loads(content)
            proxies = json.loads(info.get('proxies', None))
            ping_url = 'https://www.alipay.com/'
            status_code = requests.get(ping_url, timeout=3.1, proxies=proxies).status_code
            # status_code = 200
            if status_code == 200:
                info_logger.info(json.dumps(proxies) + 'status 200 ok')
                print("代理请求成功,耗时:【%.2fs】" % (time.time()-begin))
                return proxies
            else:
                count += 1
                info_logger.warning(json.dumps(proxies) + 'status not 200')
                continue

        info_logger.warning('try count > 5')

    except Exception as e:
        err_logger.error(str(e))
        print("代理请求失败,耗时:【%.2fs】" % (time.time() - begin))
        return None


def crack_captcha(img_b64):
    url = 'http://127.0.0.1:5010/captcha/crack/'
    data = {
        "serialNum": 'zfb001',
        "imgBase64": img_b64
    }
    content = requests.post(url, data=json.dumps(data)).content

    return json.loads(content)['captcha']


if __name__ == '__main__':
    prc = PhoneRegisterCheck()
    res = prc.check(13017202140)
    print(res)
