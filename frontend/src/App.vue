<template>
  <div class="container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>论文格式检查</h2>
        </div>
      </template>
      <div class="form-container">
        <el-form :model="form" label-width="120px">
          <el-form-item label="论文格式模板">
            <el-select 
              v-model="form.template" 
              placeholder="请选择论文格式模板"
              :disabled="isProcessing"
            >
              <el-option label="阳光学院论文格式" value="sunshine" />
              <el-option label="厦门大学论文格式" value="xmu" />
            </el-select>
          </el-form-item>
          <el-form-item label="论文文件">
            <el-upload
              ref="upload"
              class="upload-demo"
              :http-request="customUpload"
              :data="form"
              :on-success="handleSuccess"
              :on-error="handleError"
              :before-upload="beforeUpload"
              :on-remove="handleRemove"
              :on-change="handleChange"
              :auto-upload="false"
              accept=".docx"
              :disabled="isProcessing"
              :limit="1"
              :on-exceed="handleExceed"
              :file-list="fileList"
            >
              <template #trigger>
                <el-button type="primary" :disabled="isProcessing || fileList.length >= 1">选择文件</el-button>
              </template>
              <el-button
                class="ml-3"
                type="success"
                @click="submitUpload"
                :disabled="!hasFile || !form.template || isProcessing"
              >
                {{ isProcessing ? '处理中...' : '开始检查' }}
              </el-button>
            </el-upload>
            <el-progress
              v-if="uploadProgress > 0 && uploadProgress < 100"
              :percentage="uploadProgress"
              :format="progressFormat"
            />
          </el-form-item>
        </el-form>  
      </div>
      <div class="result-container">
        <h3>检查结果：</h3>
        <div v-if="result" v-html="renderResult(result)" class="result-content"></div>
        <div v-else-if="errorInfo" class="error-result">
          <h4>发生错误：</h4>
          <p class="error-message">{{ errorInfo.error }}</p>
          <p v-if="errorInfo.detail" class="error-detail">{{ errorInfo.detail }}</p>
          <div v-if="errorInfo.code === 401" class="error-solution">
            <p>可能的解决方案：</p>
            <ul>
              <li>检查 API 密钥是否正确</li>
              <li>确认 API 密钥未过期</li>
              <li>联系管理员重新配置 API 密钥</li>
            </ul>
          </div>
        </div>
        <div v-else class="empty-result">
          <p>请选择论文格式模板并上传文件进行检查</p>
        </div>
      </div>
    </el-card>
    
    <!-- 全局加载状态 -->
    <el-loading 
      v-model:full-screen="fullscreenLoading" 
      element-loading-text="正在分析论文格式，请稍候..."
      :lock="true"
    />
  </div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { ElMessage, ElLoading } from 'element-plus'
import axios from 'axios'
import MarkdownIt from 'markdown-it'
import JSZip from 'jszip'

const md = new MarkdownIt()

const form = reactive({
  template: '',
})

const hasFile = ref(false)
const result = ref('')
const errorInfo = ref(null)
const upload = ref(null)
const uploadProgress = ref(0)
const isProcessing = ref(false)
const fullscreenLoading = ref(false)
const fileList = ref([])

const progressFormat = (percentage) => {
  return percentage === 100 ? '处理中...' : `上传中 ${percentage}%`
}

// 处理超出文件数量限制
const handleExceed = (files) => {
  ElMessage.warning('最多只能上传一份论文文件')
}

// 检查文件是否已存在
const isFileExist = (file) => {
  const fileName = file.name
  return fileList.value.some(item => item.name === fileName)
}

const beforeUpload = (file) => {
  // 检查文件类型
  const isDocx = file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  if (!isDocx) {
    ElMessage.error('只能上传 .docx 格式的文件！')
    return false
  }
  
  // 检查文件是否已存在
  if (isFileExist(file)) {
    ElMessage.warning(`文件 "${file.name}" 已存在，请勿重复添加`)
    return false
  }
  
  // 检查文件数量
  if (fileList.value.length >= 1) {
    ElMessage.warning('最多只能上传一份论文文件')
    return false
  }
  
  return true
}

const handleChange = (file, fileList) => {
  hasFile.value = fileList.length > 0
  // 更新文件列表
  fileList.value = fileList
}

const handleRemove = (file, fileList) => {
  hasFile.value = fileList.length > 0
  // 更新文件列表
  fileList.value = fileList
  uploadProgress.value = 0
}

const submitUpload = () => {
  if (!form.template) {
    ElMessage.error('请选择论文格式模板！')
    return
  }
  
  if (!hasFile.value) {
    ElMessage.error('请先选择文件！')
    return
  }
  
  // 重置错误信息
  errorInfo.value = null
  result.value = ''
  
  upload.value.submit()
}

const customUpload = async (options) => {
  const { file } = options
  try {
    isProcessing.value = true
    fullscreenLoading.value = true
    
    // 检查文件大小
    if (file.size === 0) {
      throw new Error('文件内容为空，请检查文件是否有效')
    }

    // 创建新的JSZip实例
    const zip = new JSZip()
    
    // 读取文件内容并添加到zip中
    const fileContent = await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        const content = e.target.result
        if (!content || content.byteLength === 0) {
          reject(new Error('文件读取失败，获取到的内容为空'))
        }
        resolve(content)
      }
      reader.onerror = () => reject(new Error('文件读取失败'))
      reader.readAsArrayBuffer(file)
    })
    
    // 将文件内容添加到zip中
    zip.file(file.name, fileContent)
    
    // 生成zip blob
    const zipBlob = await zip.generateAsync({
      type: 'blob',
      compression: 'DEFLATE',
      compressionOptions: {
        level: 9
      }
    })
    
    // 检查生成的zip文件大小
    if (zipBlob.size === 0) {
      throw new Error('压缩后的文件大小为0，请检查文件内容')
    }
    
    // 创建FormData对象
    const formData = new FormData()
    formData.append('file', new File([zipBlob], 'document.zip', { type: 'application/zip' }))
    formData.append('template', form.template)

    try {
      const response = await axios.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          uploadProgress.value = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          )
        }
      })
      handleSuccess(response.data)
    } catch (error) {
      handleApiError(error)
    }
  } catch (error) {
    isProcessing.value = false
    fullscreenLoading.value = false
    ElMessage.error(error.message || '上传失败，请重试')
  }
}

const handleApiError = (error) => {
  isProcessing.value = false
  fullscreenLoading.value = false
  uploadProgress.value = 0
  
  // 设置错误信息
  if (error.response) {
    // 服务器返回了错误响应
    const { status, data } = error.response
    
    // 设置错误信息对象
    errorInfo.value = {
      error: data.error || `请求失败 (${status})`,
      code: data.code || status,
      detail: data.detail || '服务器返回了错误响应'
    }
    
    // 根据状态码显示不同的错误消息
    if (status === 401) {
      ElMessage.error({
        message: '认证失败：API密钥无效或已过期',
        duration: 5000
      })
    } else if (status === 503 || status === 504) {
      ElMessage.error({
        message: '服务暂时不可用，请稍后重试',
        duration: 5000
      })
    } else {
      ElMessage.error({
        message: data.error || '请求失败，请稍后重试',
        duration: 5000
      })
    }
  } else if (error.request) {
    // 请求已发送但没有收到响应
    errorInfo.value = {
      error: '无法连接到服务器',
      code: 0,
      detail: '请求已发送，但未收到服务器响应，请检查网络连接'
    }
    ElMessage.error('无法连接到服务器，请检查网络连接')
  } else {
    // 请求设置时发生错误
    errorInfo.value = {
      error: error.message || '请求错误',
      code: 0,
      detail: '发送请求时出现错误'
    }
    ElMessage.error(error.message || '请求错误')
  }
}

const handleSuccess = (response) => {
  result.value = response.result
  errorInfo.value = null
  ElMessage.success('检查完成')
  isProcessing.value = false
  fullscreenLoading.value = false
  uploadProgress.value = 0
}

const handleError = (error) => {
  handleApiError(error)
}

const renderResult = (text) => {
  // 去除多余空行
  const cleanText = text.replace(/\n\s*\n/g, '\n')
  // 使用markdown-it渲染文本
  return md.render(cleanText)
}
</script>

<style scoped>
.container {
  max-width: 1200px;
  margin: 20px auto;
  padding: 0 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-container {
  margin: 20px 0;
}

.result-container {
  margin-top: 20px;
  padding: 20px;
  background-color: #f5f7fa;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.12);
}

.result-content {
  white-space: normal;
  line-height: 1.6;
  font-size: 14px;
  color: #333;
  padding: 10px;
  background-color: #fff;
  border-radius: 4px;
  max-height: 500px;
  overflow-y: auto;
  margin-top: 10px;
}

.result-content :deep(p) {
  margin: 0.5em 0;
}

.result-content :deep(ul), .result-content :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.error-result {
  padding: 15px;
  background-color: #fff;
  border-radius: 4px;
  border-left: 4px solid #f56c6c;
  margin-top: 10px;
}

.error-message {
  color: #f56c6c;
  font-weight: bold;
  margin-bottom: 10px;
}

.error-detail {
  color: #606266;
  margin-bottom: 15px;
}

.error-solution {
  background-color: #fef0f0;
  padding: 10px 15px;
  border-radius: 4px;
  margin-top: 10px;
}

.error-solution p {
  font-weight: bold;
  margin-bottom: 5px;
}

.error-solution ul {
  padding-left: 20px;
  margin: 5px 0;
}

.ml-3 {
  margin-left: 12px;
}

.empty-result {
  text-align: center;
  color: #909399;
  padding: 20px;
}
</style> 