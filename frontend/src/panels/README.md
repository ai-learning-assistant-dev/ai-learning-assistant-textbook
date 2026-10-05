/**
 * 功能面板目录：一个子目录对应首页的一个功能栏。
 *
 * 与 components/ 的区别：
 * - components/ 是历史代码，按组件平铺；
 * - panels/ 是按首页功能栏划分，一个功能栏一个子目录，
 *   内部自包含 types / api / components，通过 index.ts 统一出口。
 *
 * 目录名与后端 services/ 下的服务名一一对应（notecard ↔ services/notecard），
 * 这样「前端某个功能栏」和「后端哪套接口」一眼就能对上。
 *
 * 新增面板时：在此新建同名子目录 → 在 App.tsx 的 PANELS 注册表登记。
 *
 * 当前面板：
 * - notecard/ 笔记制卡（左来源 / 中校验列表 / 右详情 的三栏布局）
 */
