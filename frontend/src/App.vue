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
            <el-select v-model="form.template" placeholder="请选择论文格式模板">
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
              :auto-upload="false"
              accept=".docx"
            >
              <template #trigger>
                <el-button type="primary">选择文件</el-button>
              </template>
              <el-button
                class="ml-3"
                type="success"
                @click="submitUpload"
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
        <div v-else class="empty-result">
          <p>请选择论文格式模板并上传文件进行检查</p>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import MarkdownIt from 'markdown-it'
import JSZip from 'jszip'

const md = new MarkdownIt()

const form = reactive({
  template: '',
})

const hasFile = ref(false)
const result = ref('')
const upload = ref(null)
const uploadProgress = ref(0)
const isProcessing = ref(false)

const progressFormat = (percentage) => {
  return percentage === 100 ? '处理中...' : `上传中 ${percentage}%`
}

const beforeUpload = (file) => {
  const isDocx = file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  if (!isDocx) {
    ElMessage.error('只能上传 .docx 格式的文件！')
    return false
  }
  hasFile.value = true
  return true
}

const handleRemove = () => {
  hasFile.value = false
  uploadProgress.value = 0
}

const submitUpload = () => {
  if (!form.template) {
    ElMessage.error('请选择论文格式模板！')
    return
  }
  upload.value.submit()
}

const customUpload = async (options) => {
  const { file } = options
  try {
    isProcessing.value = true
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
    isProcessing.value = false
    ElMessage.error(error.message || '上传失败，请重试')
  }
}

const handleSuccess = (response) => {
  result.value = response.result
  ElMessage.success('检查完成')
  isProcessing.value = false
  uploadProgress.value = 0
}

const handleError = () => {
  ElMessage.error('上传失败，请重试')
  isProcessing.value = false
  uploadProgress.value = 0
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

.ml-3 {
  margin-left: 12px;
}
</style>