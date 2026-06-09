import { expect, test } from '@playwright/test'
import { writeFileSync } from 'node:fs'

test('mobile upload flow renders completed prompt result', async ({ page }, testInfo) => {
  await page.route('**/api/health', async (route) => {
    await route.fulfill({
      json: {
        ok: true,
        model: 'MiniMax-M3',
        files_api_enabled: false,
        max_upload_mb: 45,
        max_concurrent_jobs: 1,
        job_retention_hours: 72,
      },
    })
  })

  await page.route('**/api/jobs/job-1', async (route) => {
    await route.fulfill({
      json: {
        id: 'job-1',
        status: 'completed',
        filename: 'sample.mp4',
        size_bytes: 12,
        prompt_mode: 'standard',
        language: 'zh',
        progress: 100,
        message: '提示词生成完成',
        result: {
          summary: '一段手机拍摄的示例视频',
          subject: '一名人物',
          scene: '室内场景',
          action: '缓慢移动',
          camera: '手持跟拍',
          lighting: '自然光',
          style: '写实',
          seedance_prompt: '一名人物在室内自然光下缓慢移动，手持跟拍，写实清晰画质。',
          storyboard_prompt: '镜头1：人物出现在室内。',
          negative_prompt: '畸形、闪烁、水印',
          english_prompt: 'A realistic handheld indoor shot.',
          raw_text: '',
        },
        error: null,
        created_at: 1,
        updated_at: 2,
        meta: {},
      },
    })
  })

  await page.route('**/api/jobs', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ json: { job_id: 'job-1', status: 'queued' } })
      return
    }
    await route.fulfill({
      json: [
        {
          id: 'job-1',
          status: 'completed',
          filename: 'sample.mp4',
          size_bytes: 12,
          prompt_mode: 'standard',
          language: 'zh',
          progress: 100,
          message: '提示词生成完成',
          result: null,
          error: null,
          created_at: 1,
          updated_at: 2,
          meta: {},
        },
      ],
    })
  })

  await page.goto('/')
  await expect(page.getByRole('heading', { name: '视频转即梦提示词' })).toBeVisible()
  await expect(page.getByText('MiniMax-M3 · 最大 45MB · 并发 1')).toBeVisible()

  const videoPath = testInfo.outputPath('sample.mp4')
  writeFileSync(videoPath, Buffer.from('fake video'))
  await page.locator('input[type="file"]').setInputFiles(videoPath)
  await expect(page.locator('.file-meta')).toContainText('sample.mp4')

  await page.getByRole('button', { name: '开始生成提示词' }).click()
  await expect(page.locator('.progress-card').last()).toContainText('提示词生成完成')
  await expect(page.getByText('即梦一键粘贴版')).toBeVisible()
  await expect(page.locator('.prompt-editor')).toHaveValue(/一名人物在室内自然光下缓慢移动/)
  await expect(page.getByRole('heading', { name: '最近任务' })).toBeVisible()
})
