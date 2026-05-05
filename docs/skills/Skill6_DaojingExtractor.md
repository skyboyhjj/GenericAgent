# Skill 6: 道德经内容提取与处理

> **所属方法论**：慧惠开发方法论 Skills v1.1.0  
> **Skill 编号**：Skill 6  
> **验证状态**：✅ S2 验证通过（8/8 测试用例全部通过）  
> **最后更新**：2026年5月5日  
> **核心文件**：`GenericAgent/tools/DaojingExtractor.js`（约710行）

---

## 一、适用场景

从非结构化的长篇报告文档（如81章《道德经》五步协同读解报告）中，批量提取结构化知识数据，生成：
1. **章节数据库** — 81章完整镜鉴数据（dimensions + empowerment + SPO triples）
2. **SPO 知识图谱索引** — subject / predicate / object 三元组知识网络
3. **道商维度定义库** — 15维度道商（DQ）定义与章节映射

适用于以下情况：
- 需要将大量非结构化文本（学术报告、古籍译注、分析文档）数字化为结构化知识库
- 源文件存在多种格式变体（不同作者、不同时期产出的格式不一致）
- 目标产物需要同时服务多个下游系统（小程序、API、知识图谱数据库）
- 提取过程需要可验证、可回滚、零破坏（不修改源文件和现有代码）

---

## 二、核心流程（5步管道）

```
Markdown 报告文件（25个 .md）
    ↓  ① 数据加载 — 递归扫描目录，双层级章节分隔（#/##）
JSON 区块提取
    ↓  ② 关键词提取 — SPO三元组解析（双格式兼容）+ 赋能方案匹配
结构化中间数据（内存）
    ↓  ③ 维度评分 — P忠恕四维模型注入 + 道商维度关联 + 跨章节索引
81章完整数据库
    ↓  ④ 增量注入 — daojing_database_v2.js（349KB）+ SPO索引（146KB）+ DQ维度（6KB）
小程序数据层
    ↓  ⑤ 结果输出 — 3个产物文件写入 miniprogram/data/daojing/
```

### 2.1 数据加载（步骤一）

**输入**：`daodejing-output/reports/` 下 25 个 Markdown 文件（上经10个 + 下经15个）

**关键挑战**：
- 文件间章节级别不一致：上经使用 `## 第X章`（H2），下经使用 `# 第X章`（H1）
- 章节编号方式不一致：上经混合阿拉伯数字和中文数字（如 `第十九章`）
- 文件级标题干扰：如 `# 《道德经》第38—40章…` 不应被识别为章节边界

**解决方案**：
```javascript
// 双层级分隔模式：同时匹配 # 和 ##
var CHAPTER_SPLIT_PATTERN = /^#{1,2}\s*第(?:\d+|[一二三四五六七八九十百]+)章/;

// 跳过文件级标题（以《道德经》开头）
var SKIP_PATTERN = /^#\s*《道德经》/;

// 中文数字→阿拉伯数字转换
_cnToArabic(cnStr) {
  // "十九" → "19", "二十一" → "21", "八十" → "80"
}
```

**输出**：81个章节文本块，按章节ID（1-81）索引

### 2.2 关键词提取（步骤二）

**输入**：每章文本块中的 JSON 代码块

**关键挑战**：
- SPO 格式双版本：上经用 `spo_triples/subject/predicate/object`，下经用 `triples/S/P/O`
- 赋能方案标题多种写法：`### 对「袭明镜鉴」的赋能方案` / `### 赋能方案` / `#### 赋能方案`

**解决方案**：
```javascript
// 双格式归一化
var rawTriples = data.spo_triples || data.triples || [];
normalizedTriples.push({
  subject: tr.subject || tr.S || '',
  subject_type: tr.subject_type || tr.subjectType || '概念',
  predicate: tr.predicate || tr.P || '',
  relation_type: tr.relation_type || tr.relationType || tr.relation || '关联',
  object: tr.object || tr.O || '',
  object_type: tr.object_type || tr.objectType || '概念',
  context: tr.context || '',
});

// 多模式赋能方案匹配
var sectionHeader: /(?:### )?(?:三、 )?对["「]?袭明镜鉴["」]?(?:小程序)?的赋能方案|## 赋能方案/,
```

**输出**：572 条 SPO 三元组，15 套赋能方案（daily_mirror + concept_cards + dq_dimensions）

### 2.3 维度评分（步骤三）

P忠恕四维模型注入到每章数据结构：

| 维度        | 物理含义 | 权重 | 两级镜鉴 |
| :---------- | :------- | :--- | :------- |
| 时位轴（T） | 时间方位 | 0.2  | 低/高    |
| 宇位轴（S） | 空间方位 | 0.2  | 低/高    |
| 识位轴（C） | 认知层级 | 0.3  | 低/高    |
| 缘位轴（R） | 关系层级 | 0.3  | 低/高    |

同时构建：
- **关键词倒排索引**：108个核心概念 → 章节映射
- **SPO 概念索引**：384个唯一 subject → 所属章节
- **关系类型统计**：26种关系类型分布

### 2.4 增量注入（步骤四）

遵循"善行无辙迹"原则——**只新增文件，不修改现有代码**：

| 文件                       | 类型 | 大小     | 用途            |
| :------------------------- | :--- | :------- | :-------------- |
| `daojing_database_v2.js`   | 新增 | 349.1 KB | 81章完整数据库  |
| `daojing_spo_index.json`   | 新增 | 145.9 KB | SPO知识图谱索引 |
| `daojing_dq_dimensions.js` | 新增 | 5.5 KB   | 道商维度定义库  |
| `daojingSchema.js`         | 新增 | 6.7 KB   | 数据格式校验层  |
| `daojingMigrator.js`       | 新增 | 5.8 KB   | V1→V2迁移工具   |

**零破坏验证**：`daojingMatcher.js`, `daojingStorage.js`, `daojingConstants.js`, `daojingDataLoader.js`, `daojingService.js`, `daojingAnalyzer.js` — **全部未修改**。

### 2.5 结果输出（步骤五）

3个产物文件写入 `miniprogram/data/daojing/`，供微信小程序直接 `require()` 加载。

校验管线：
```
daojing_database_v2.js
    ↓ daojingSchema.quickValidate()
格式校验（结构 + 四维 + SPO + 赋能方案）
    ↓ daojingMigrator.migrate()
V1→V2 迁移（兼容 + 可回滚）
    ↓ daojing_extractor.test.js
8项端到端验证（全部通过）
```

---

## 三、在慧惠项目中的实践

### 3.1 与现有小程序代码的关系

```
miniprogram/utils/daojing/
├── daojingStorage.js      ← 用户记录存储（不改）
├── daojingConstants.js    ← 维度/停用词/触发权重（不改）
├── daojingDataLoader.js   ← V1 数据库加载器（不改）
├── daojingMatcher.js      ← 文本→关键词→维度→镜鉴（不改）
├── daojingService.js      ← 服务封装（不改）
├── daojingAnalyzer.js     ← P级评估 + 趋势分析（不改）
├── daojingSchema.js       ★ 新增：数据校验层
└── daojingMigrator.js     ★ 新增：V1→V2迁移工具

miniprogram/data/daojing/
├── daojing_database.js    ← V1（10章，不改）
├── daojing_database_v2.js ★ 新增：81章完整数据库
├── daojing_spo_index.json ★ 新增：SPO知识图谱索引
└── daojing_dq_dimensions.js ★ 新增：道商维度定义库
```

### 3.2 道家AI伦理落地实例

| 理念         | 产品含义                   | 工程实现                                               |
| :----------- | :------------------------- | :----------------------------------------------------- |
| 无为而无不为 | 全流程自动化，无需人工干预 | 单命令运行 `node DaojingExtractor.js`，3个产物自动生成 |
| 善行无辙迹   | 零破坏注入                 | 2个新工具文件 + 3个新数据文件，原有6个文件零修改       |
| 为道日损     | 中间数据用后即焚           | 脚本运行时的内存数据结构不落盘，仅保留3个最终产物      |
| 善数不用筹策 | 校验逻辑简洁直观           | `daojingSchema.js` 仅约170行，不引入任何测试框架依赖   |

### 3.3 多格式容错能力

本次提取面对的源文件格式异构性：

| 差异维度     | 上经（37章）                               | 下经（44章）        |
| :----------- | :----------------------------------------- | :------------------ |
| 章节标题层级 | `## 第X章`（H2）                           | `# 第X章`（H1）     |
| 章节编号方式 | 混合阿拉伯/中文数字                        | 阿拉伯数字          |
| SPO JSON key | `spo_triples` / `subject/predicate/object` | `triples` / `S/P/O` |
| 赋能方案标题 | `三、对「袭明镜鉴」的赋能方案`             | `### 赋能方案`      |

提取器通过"容错归一化"策略（优先尝试标准格式，回退到备选格式），实现了 81/81 章的全量覆盖。

---

## 四、可复用模板

当遇到"从非结构化报告批量提取结构化知识数据"的需求时，按以下步骤操作：

### 步骤一：准备源文件目录

将报告文件（不限Markdown格式）统一放置在一个目录下。提取器支持递归扫描，不要求扁平结构。

### 步骤二：编写提取器骨架

```javascript
// 1. 定义章节分隔模式
var CHAPTER_SPLIT_PATTERN = /正则表达式/;

// 2. 定义提取目标模式
var EXTRACT_PATTERN = { ... };

// 3. 实现 _splitIntoChapters(content)
// 4. 实现 _parseChapterBlock(block)
// 5. 实现 _normalizeData(raw) — 多格式归一化
// 6. 实现 _buildIndex(database) — 构建倒排索引
// 7. 实现 _writeOutput(database, indexes) — 写入产物文件
```

### 步骤三：处理格式异构

为每个可能存在差异的字段编写归一化逻辑：

```javascript
// 容错归一化模式
var subject = tr.subject || tr.S || tr.s || '';
var predicate = tr.predicate || tr.P || tr.p || tr.relation || '';
var object = tr.object || tr.O || tr.o || '';
```

### 步骤四：编写校验层

至少包含：
1. **结构校验** — 必需的顶层字段是否存在
2. **完整性校验** — 期望的条目数量是否达标
3. **类型校验** — 字段类型是否符合预期

### 步骤五：编写验证脚本

覆盖至少5类场景：
1. 全量提取（条目数 = 期望数）
2. 子结构完整性（每条的必需字段齐全）
3. 交叉引用一致性（索引与实际数据相符）
4. 零破坏验证（源文件和现有代码未被修改）
5. 向后兼容（新版数据可被旧版加载器使用）

---

## 五、关键原则

### 5.1 容错优先于报错

源文件格式的异构性应在提取器中消化，而非要求源文件规范化。宁可多写3行归一化代码，也不要为了1种格式的纯净而放弃10个有效文件。

### 5.2 零破坏注入

新增功能永远只新增文件，不要修改现有文件（除非显式需要修改钩子点）。这是"善行无辙迹"的工程表达。

### 5.3 输出即交付

提取器的产物文件应可直接被下游系统使用（本例中直接放入 `miniprogram/data/` 目录），无需二次处理。产物文件名、路径、导出格式应与下游系统的 `require()` 习惯一致。

### 5.4 校验与提取分离

提取逻辑（`DaojingExtractor.js`）与校验逻辑（`daojingSchema.js`）应解耦。提取器负责"怎么取"，校验器负责"取得对不对"。后续如果需要新增数据源，只需更新提取器，校验器可复用。

### 5.5 迁移需可回滚

从旧格式到新格式的迁移工具必须提供 `rollback()` 方法。"善行无辙迹"也意味着：如果新数据有问题，用户应能一键回到旧状态。

---

## 六、验收清单

- [ ] 提取器运行无报错（退出码 0）
- [ ] 产物文件全部生成（3个或以上）
- [ ] 全量提取（期望条目数全部覆盖）
- [ ] 每章必需字段齐全（chapter_title, dimensions, spo_triples, empowerment）
- [ ] 校验层 `quickValidate()` 返回 `{ valid: true }`
- [ ] 迁移工具 `migrate()` 返回 `{ success: true }`
- [ ] 验证脚本全部测试通过（退出码 0）
- [ ] 源文件未被修改（零破坏）
- [ ] 现有代码未被修改（零破坏）
- [ ] 回滚功能可用（`rollback()` 返回 `{ success: true }`）

---

## 七、文件清单

| 文件路径                                            | 行数 | 类型     | 说明                        |
| :-------------------------------------------------- | :--- | :------- | :-------------------------- |
| `GenericAgent/tools/DaojingExtractor.js`            | ~710 | 提取器   | 核心提取引擎（Node.js脚本） |
| `miniprogram/utils/daojing/daojingSchema.js`        | ~170 | 校验层   | 数据格式校验                |
| `miniprogram/utils/daojing/daojingMigrator.js`      | ~155 | 迁移工具 | V1→V2迁移 + 回滚            |
| `miniprogram/test/daojing_extractor.test.js`        | ~260 | 验证脚本 | 8项端到端测试               |
| `miniprogram/data/daojing/daojing_database_v2.js`   | —    | 数据产物 | 81章镜鉴数据库（349.1KB）   |
| `miniprogram/data/daojing/daojing_spo_index.json`   | —    | 数据产物 | SPO知识图谱索引（145.9KB）  |
| `miniprogram/data/daojing/daojing_dq_dimensions.js` | —    | 数据产物 | 道商维度定义库（5.5KB）     |

---

## 八、执行命令

```bash
# 提取（使用默认路径）
node GenericAgent/tools/DaojingExtractor.js

# 提取（指定源目录和输出目录）
node GenericAgent/tools/DaojingExtractor.js \
  --reports-dir=daodejing-output/reports \
  --output-dir=Ximing-master20260409/miniprogram/data/daojing

# 验证
node Ximing-master20260409/miniprogram/test/daojing_extractor.test.js
```

---

*本文档是慧惠开发方法论 Skills 体系的第6个 Skill。随着慧惠项目的推进，新的数据提取需求可参照此模板执行。*
