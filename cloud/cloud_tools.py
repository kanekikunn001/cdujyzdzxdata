import json
import os
import time
from datetime import datetime
from qcloud_cos import CosConfig, CosS3Client
from qcloud_cos.cos_exception import CosServiceError


class CloudBackupManager:
    def __init__(self, config_file="configuration_file/cloud_configuration_file.json"):
        self.config_file = config_file
        self.load_config(config_file)
        self.setup_cos_client()
    
    def load_config(self, config_file):
        """加载云配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.cos_config = config.get('tencent_cloud', {}).get('cos', {})
            self.backup_config = config.get('backup', {})
            self.data_config = config.get('nimi_program_data', {})
            self.feedback_config = config.get('feedback', {})
            print("✅ 云配置加载成功")
        except Exception as e:
            print(f"❌ 云配置加载失败: {e}")
            raise
    
    def setup_cos_client(self):
        """初始化COS客户端"""
        try:
            secret_id = self.cos_config['secret_id']
            secret_key = self.cos_config['secret_key']
            region = self.cos_config['region']
            
            config = CosConfig(
                Region=region,
                SecretId=secret_id,
                SecretKey=secret_key,
                Scheme=self.cos_config.get('scheme', 'https'),
                Timeout=self.cos_config.get('timeout', 60)
            )
            self.client = CosS3Client(config)
            self.bucket = self.cos_config['bucket']
            print("✅ COS客户端初始化成功")
        except Exception as e:
            print(f"❌ COS客户端初始化失败: {e}")
            raise
    
    def upload_file(self, local_file, cloud_key):
        """上传文件到云端"""
        try:
            if not os.path.exists(local_file):
                print(f"❌ 本地文件不存在: {local_file}")
                return False
            
            # 获取文件大小
            file_size = os.path.getsize(local_file)
            print(f"📤 上传文件: {local_file} ({file_size} bytes) -> {cloud_key}")
            
            response = self.client.put_object_from_local_file(
                Bucket=self.bucket,
                LocalFilePath=local_file,
                Key=cloud_key
            )
            print(f"✅ 上传成功: {cloud_key}")
            return True
        except CosServiceError as e:
            print(f"❌ 上传失败 (COS错误): {e.get_error_code()} - {e.get_error_msg()}")
            return False
        except Exception as e:
            print(f"❌ 上传失败: {e}")
            return False
    
    def download_file(self, cloud_key, local_file):
        """从云端下载文件"""
        try:
            # 创建本地目录
            local_dir = os.path.dirname(local_file)
            if local_dir and not os.path.exists(local_dir):
                os.makedirs(local_dir, exist_ok=True)
            
            print(f"📥 下载文件: {cloud_key} -> {local_file}")
            
            response = self.client.download_file(
                Bucket=self.bucket,
                Key=cloud_key,
                DestFilePath=local_file
            )
            print(f"✅ 下载成功: {local_file}")
            return True
        except CosServiceError as e:
            print(f"❌ 下载失败 (COS错误): {e.get_error_code()} - {e.get_error_msg()}")
            return False
        except Exception as e:
            print(f"❌ 下载失败: {e}")
            return False
    
    def get_cloud_file_info(self, cloud_key):
        """获取云端文件信息（包括最后修改时间）"""
        try:
            response = self.client.head_object(
                Bucket=self.bucket,
                Key=cloud_key
            )
            last_modified = response.get('Last-Modified', '')
            return {
                'exists': True,
                'last_modified': last_modified,
                'etag': response.get('ETag', ''),
                'size': response.get('Content-Length', 0)
            }
        except CosServiceError as e:
            if e.get_status_code() == 404:
                return {'exists': False}
            else:
                print(f"❌ 获取文件信息失败: {e.get_error_code()} - {e.get_error_msg()}")
                return {'exists': False}
        except Exception as e:
            print(f"❌ 获取文件信息失败: {e}")
            return {'exists': False}
    
    def compare_versions(self, local_version_file, cloud_version_key):
        """比较本地和云端版本"""
        try:
            # 读取本地版本
            local_version = {}
            if os.path.exists(local_version_file):
                with open(local_version_file, 'r', encoding='utf-8') as f:
                    local_version = json.load(f)
            
            # 获取云端版本
            cloud_version = {}
            temp_cloud_file = f"temp_{os.path.basename(local_version_file)}"
            if self.download_file(cloud_version_key, temp_cloud_file):
                if os.path.exists(temp_cloud_file):
                    with open(temp_cloud_file, 'r', encoding='utf-8') as f:
                        cloud_version = json.load(f)
                    os.remove(temp_cloud_file)
            
            local_time = local_version.get('last_updated', '')
            cloud_time = cloud_version.get('last_updated', '')
            
            if not local_time and not cloud_time:
                return 'equal'
            elif not local_time:
                return 'cloud_newer'
            elif not cloud_time:
                return 'local_newer'
            else:
                # 比较时间戳
                local_dt = datetime.strptime(local_time, '%Y-%m-%d %H:%M:%S')
                cloud_dt = datetime.strptime(cloud_time, '%Y-%m-%d %H:%M:%S')
                if local_dt > cloud_dt:
                    return 'local_newer'
                elif cloud_dt > local_dt:
                    return 'cloud_newer'
                else:
                    return 'equal'
                    
        except Exception as e:
            print(f"❌ 版本比较失败: {e}")
            return 'unknown'
    
    def sync_data_to_cloud(self):
        """同步数据到云端"""
        try:
            # 同步小程序数据
            data_dir = self.data_config.get('local_data_dir', 'mini_program_data')
            cloud_prefix = self.data_config.get('cloud_data_prefix', 'data/')
            
            files_to_sync = ['scheduling_data.json', 'scheduling_list.json', 'time_list.json', 'version.json']
            
            for filename in files_to_sync:
                local_file = os.path.join(data_dir, filename)
                cloud_key = cloud_prefix + filename
                
                if os.path.exists(local_file):
                    self.upload_file(local_file, cloud_key)
                else:
                    print(f"⚠️ 文件不存在，跳过: {local_file}")
            
            # 同步数据库备份
            backup_dir = self.backup_config.get('local_backup_dir', 'backup/database')
            if os.path.exists(backup_dir):
                for backup_file in os.listdir(backup_dir):
                    if backup_file.endswith('.db'):
                        local_backup = os.path.join(backup_dir, backup_file)
                        cloud_backup_key = self.backup_config.get('cloud_backup_prefix', 'database_backups/') + backup_file
                        self.upload_file(local_backup, cloud_backup_key)
            
            print("✅ 数据同步到云端完成")
            return True
            
        except Exception as e:
            print(f"❌ 数据同步失败: {e}")
            return False
    
    def sync_data_from_cloud(self):
        """从云端同步数据"""
        try:
            data_dir = self.data_config.get('local_data_dir', 'mini_program_data')
            cloud_prefix = self.data_config.get('cloud_data_prefix', 'data/')
            
            files_to_sync = ['scheduling_data.json', 'scheduling_list.json', 'time_list.json', 'version.json']
            
            for filename in files_to_sync:
                cloud_key = cloud_prefix + filename
                local_file = os.path.join(data_dir, filename)
                
                file_info = self.get_cloud_file_info(cloud_key)
                if file_info['exists']:
                    self.download_file(cloud_key, local_file)
                else:
                    print(f"⚠️ 云端文件不存在，跳过: {cloud_key}")
            
            print("✅ 从云端同步数据完成")
            return True
            
        except Exception as e:
            print(f"❌ 从云端同步数据失败: {e}")
            return False