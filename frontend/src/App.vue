<template>
  <div class="container">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <h2>论文格式检查工具</h2>
        </div>
      </template>
      <div class="form-container">
        <el-form :model="form" label-width="120px">
          <el-form-item label="论文格式模板">
            <el-select v-model="form.template" placeholder="请选择论文格式模板">
              <el-option label="阳光学院" value="sunshine" />
              <el-option label="厦门大学" value="xmu" />
            </el-select>
          </el-form-item>
          <el-form-item label="论文文件">
            <el-upload
              class="upload-demo"
              action="/api/upload"
              :on-success="handleSuccess"
              :on-error="handleError"
              :before-upload="beforeUpload"
              accept=".docx"
              :auto-upload="false"
              ref="upload"
            >
              <template #trigger>
                <el-button type="primary">选择文件</el-button>
              </template>
              <el-button
                class="ml-3"
                type="success"
                @click="submitUpload"
                :disabled="!form.template || !hasFile"
              >
                开始检查
              </el-button>
            </el-upload>
          </el-form-item>
        </el-form>
      </div>
      <div v-if="result" class="result-container">
        <h3>检查结果：</h3>
        <div v-html="result" class="result-content"></div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const form = reactive({
  template: '',
})

const hasFile = ref(false)
const result = ref('')
const upload = ref(null)

const beforeUpload = (file) => {
  hasFile.value = true
  const isDocx = file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  if (!isDocx) {
    ElMessage.error('只能上传 .docx 格式的文件！')
    return false
  }
  return true
}

const submitUpload = () => {
  if (!form.template) {
    ElMessage.error('请选择论文格式模板！')
    return
  }
  upload.value.submit()
}

const handleSuccess = (response) => {
  result.value = response.result
  ElMessage.success('检查完成')
}

const handleError = () => {
  ElMessage.error('上传失败，请重试')
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
}

.result-content {
  white-space: pre-wrap;
  line-height: 1.6;
}

.ml-3 {
  margin-left: 12px;
}
</style>