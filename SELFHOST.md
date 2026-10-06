# 自托管

本分支使用 Docker 构建源码，并通过 Nginx 提供 `/zhihu_web/` 下的静态页面。镜像发布到：

```text
ghcr.io/rogerma12345/zhihu_web
```

镜像包含 `linux/amd64` 和 `linux/arm64` 两个平台。直接运行：

```bash
docker run -d \
  --name zhihu-web \
  --restart unless-stopped \
  -p 8080:80 \
  ghcr.io/rogerma12345/zhihu_web:latest
```

浏览器打开：

```text
http://服务器地址:8080/zhihu_web/
```

登录信息仍由浏览器端处理。容器没有登录后端，不应保存知乎密码、短信验证码、Cookie 或访问令牌。

## 自动同步

`.github/workflows/sync-ghcr.yml` 每天检查一次上游，也支持手动运行。直接推送到 `main` 时只验证并发布当前分支，不执行上游同步。

自动同步以 `.upstream-state` 记录的上游提交为三方合并基准。应用源码若能自动合并，就继续执行测试、构建和镜像发布；发生冲突时立即停止，不向仓库提交结果。只有测试、构建和镜像发布全部成功后，工作流才更新 `.upstream-state` 并推送同步提交。

以下部署文件不接受上游自动修改：

- `Dockerfile`
- `.dockerignore`
- `deploy/`
- `.upstream-state`
- `SELFHOST.md`
- `.github/workflows/`

上游工作流不会复制到本分支。若上游开始修改其他受保护路径，同步会失败，需要在本分支人工处理。

手动运行时，`force_build` 可在上游没有更新时重新构建当前分支。
