/**
 * DaojingExtractor — 道德经内容提取与处理引擎
 *
 * 从81章五步读解报告中提取结构化数据，生成：
 *   1. daojing_database_v2.js  — 81章完整镜鉴数据库
 *   2. daojing_spo_index.json   — SPO V3.0 知识图谱索引
 *   3. daojing_dq_dimensions.js — 道商维度（DQ）定义库
 *
 * 设计哲学（道家AI伦理）：
 *   · 无为而无不为 — 自动化全流程，人工仅需确认最终产物
 *   · 善行无辙迹   — 零破坏注入，不修改现有文件
 *   · 为道日损     — 中间数据用后即焚，仅保留结构化产物
 *
 * 用法: node DaojingExtractor.js [--reports-dir=PATH] [--output-dir=PATH]
 */

'use strict';

const fs = require('fs');
const path = require('path');

// ============================================================
// 一、配置与常量
// ============================================================

const DEFAULTS = {
    reportsDir: path.resolve(__dirname, '..', '..', 'daodejing-output', 'reports'),
    outputDir: path.resolve(__dirname, '..', '..', 'Ximing-master20260409', 'miniprogram', 'data', 'daojing'),
};

// 赋能方案各子模块的标题模式（兼容多种格式变体）
const EMPOWERMENT_PATTERNS = {
    sectionHeader: /(?:###\s*)?(?:三、\s*)?对[""\u300c\u300d]?袭明镜鉴[""\u300c\u300d]?(?:小程序)?的赋能方案|###\s*赋能方案|####\s*赋能方案/,
    dailyWisdom: /\*\*今日道家智慧\*\*[：:]\s*(.+)/,
    mirrorQuestion: /\*\*镜鉴问题\*\*[：:]\s*(.+)/,
    dailyPractice: /\*\*今日实践\*\*[：:]\s*(.+)/,
};

// SPO JSON block 模式
const SPO_JSON_PATTERN = /```json\s*\n([\s\S]*?)\n```/;

// 章节标题模式（兼容 # 和 ## 级别，兼容阿拉伯数字和中文数字）
const CHAPTER_HEADER_PATTERN = /^#{1,2}\s*第(\d+|[一二三四五六七八九十百]+)章\s*(.+)$/m;
const CHAPTER_SPLIT_PATTERN = /^#{1,2}\s*第(?:\d+|[一二三四五六七八九十百]+)章/;

// ============================================================
// 二、核心类：DaojingExtractor
// ============================================================

class DaojingExtractor {
    constructor(options = {}) {
        this.reportsDir = options.reportsDir || DEFAULTS.reportsDir;
        this.outputDir = options.outputDir || DEFAULTS.outputDir;
        this.stats = {
            filesRead: 0,
            chaptersParsed: 0,
            spoTriplesExtracted: 0,
            empowermentModulesExtracted: 0,
            errors: [],
            startTime: Date.now(),
        };
    }

    // --- 2.1 主流程 ---

    async run() {
        console.log('[DaojingExtractor] 启动 道德经内容提取引擎');
        console.log('  报告目录: ' + this.reportsDir);
        console.log('  输出目录: ' + this.outputDir);

        const files = this._discoverFiles();
        console.log('  发现 ' + files.length + ' 个报告文件');

        const allChapters = [];
        for (const file of files) {
            const chapters = this._parseFile(file);
            allChapters.push(...chapters);
            this.stats.filesRead++;
        }

        allChapters.sort((a, b) => parseInt(a.id) - parseInt(b.id));
        this.stats.chaptersParsed = allChapters.length;
        console.log('  解析完成: ' + allChapters.length + ' 章');

        this._generateDatabaseV2(allChapters);
        this._generateSpoIndex(allChapters);
        this._generateDqDimensions(allChapters);

        this.stats.elapsed = Date.now() - this.stats.startTime;
        console.log('\n[DaojingExtractor] 完成 (' + this.stats.elapsed + 'ms)');
        console.log('  章节: ' + this.stats.chaptersParsed + '/81');
        console.log('  SPO三元组: ' + this.stats.spoTriplesExtracted);
        console.log('  赋能模块: ' + this.stats.empowermentModulesExtracted);
        if (this.stats.errors.length > 0) {
            console.log('  错误: ' + this.stats.errors.length);
            this.stats.errors.slice(0, 5).forEach(function (e) { console.log('    ⚠ ' + e); });
        }
        return this.stats;
    }

    // --- 2.2 文件发现 ---

    _discoverFiles() {
        var results = [];
        var self = this;
        function walk(dir) {
            if (!fs.existsSync(dir)) return;
            var entries = fs.readdirSync(dir, { withFileTypes: true });
            for (var i = 0; i < entries.length; i++) {
                var entry = entries[i];
                var fullPath = path.join(dir, entry.name);
                if (entry.isDirectory()) {
                    walk(fullPath);
                } else if (entry.name.endsWith('.md') && entry.name.indexOf('五步读解') >= 0) {
                    results.push(fullPath);
                }
            }
        }
        walk(this.reportsDir);
        return results;
    }

    // --- 2.3 文件解析 ---

    _parseFile(filePath) {
        var content = fs.readFileSync(filePath, 'utf-8');
        var chapters = [];
        var chapterBlocks = this._splitIntoChapters(content);

        for (var i = 0; i < chapterBlocks.length; i++) {
            try {
                var chapter = this._parseChapterBlock(chapterBlocks[i]);
                if (chapter && chapter.id) {
                    chapters.push(chapter);
                }
            } catch (err) {
                this.stats.errors.push(path.basename(filePath) + ': ' + err.message);
            }
        }
        return chapters;
    }

    _splitIntoChapters(content) {
        var lines = content.split('\n');
        var blocks = [];
        var currentBlock = [];
        var inChapter = false;
        var SKIP_PATTERN = /^#\s*《道德经》/;

        for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            if (line.match(CHAPTER_SPLIT_PATTERN) && !line.match(SKIP_PATTERN)) {
                if (inChapter && currentBlock.length > 0) {
                    blocks.push(currentBlock.join('\n'));
                }
                currentBlock = [line];
                inChapter = true;
            } else if (inChapter) {
                currentBlock.push(line);
            }
        }
        if (inChapter && currentBlock.length > 0) {
            blocks.push(currentBlock.join('\n'));
        }
        return blocks;
    }

    _parseChapterBlock(block) {
        var headerMatch = block.match(CHAPTER_HEADER_PATTERN);
        if (!headerMatch) return null;

        var chapterId = this._cnToArabic(headerMatch[1]);
        var chapterTitle = headerMatch[2].trim();
        var originalText = this._extractOriginalText(block);
        var spoData = this._extractSpoTriples(block, chapterId);
        var empowerment = this._extractEmpowerment(block);

        return {
            id: chapterId,
            chapter_title: this._normalizeTitle(chapterId, chapterTitle),
            original_text: originalText,
            spo_triples: spoData ? (spoData.spo_triples || []) : [],
            core_concepts: spoData ? (spoData.core_concepts || []) : [],
            relation_network: spoData ? (spoData.relation_network || '') : '',
            empowerment: empowerment,
        };
    }

    _normalizeTitle(chapterId, rawTitle) {
        var cleaned = rawTitle.replace(/[（(][^)）]*[)）]/g, '').trim();
        return cleaned.substring(0, 18).replace(/[，,。！？\s]+$/, '');
    }

    // 中文数字 → 阿拉伯数字转换（支持"十九""二十一"等）
    _cnToArabic(cnStr) {
        if (/^\d+$/.test(cnStr)) return cnStr;
        var cnMap = { '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10 };
        var result = 0;
        var idx = cnStr.indexOf('十');
        if (idx >= 0) {
            var left = cnStr.substring(0, idx);
            var right = cnStr.substring(idx + 1);
            if (left === '') result = 10;
            else result = (cnMap[left] || 0) * 10;
            if (right) result += (cnMap[right] || 0);
        } else {
            result = cnMap[cnStr] || 0;
        }
        return String(result || cnStr);
    }

    // --- 2.4 原文提取 ---

    _extractOriginalText(block) {
        var lines = block.split('\n');
        var capture = false;
        var textLines = [];

        for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            if (line.indexOf('**原文**') >= 0 || line.indexOf('**原文') >= 0) {
                capture = true;
                continue;
            }
            if (capture) {
                if (line.match(/^\*\*|^###|^---|^#/) || (line.trim() === '' && textLines.length > 0)) {
                    break;
                }
                var cleaned = line.replace(/\*\*/g, '').trim();
                if (cleaned && /[\u4e00-\u9fa5]/.test(cleaned)) {
                    textLines.push(cleaned);
                }
            }
        }
        var result = textLines.join('');
        return result.substring(0, 500);
    }

    // --- 2.5 SPO 三元组提取（兼容双格式） ---

    _extractSpoTriples(block, chapterId) {
        var jsonMatch = block.match(SPO_JSON_PATTERN);
        var rawJson = null;

        if (jsonMatch) {
            rawJson = jsonMatch[1];
        } else {
            var altMatch = block.match(/\{[\s\S]*?"chapter":\s*\d+[\s\S]*?(?:"spo_triples"|"triples")[\s\S]*?\}/);
            if (altMatch) rawJson = altMatch[0];
        }

        if (!rawJson) return null;

        // 多轮尝试解析
        var data = null;
        var attempts = [
            rawJson,
            rawJson.replace(/,\s*\n\s*([}\]])/g, '\n$1'),
            rawJson.replace(/[\u201c\u201d]/g, '"').replace(/[\u2018\u2019]/g, "'"),
        ];

        for (var a = 0; a < attempts.length; a++) {
            try {
                data = JSON.parse(attempts[a]);
                break;
            } catch (e) {
                continue;
            }
        }

        if (!data) {
            this.stats.errors.push('第' + chapterId + '章 SPO JSON 解析失败');
            return null;
        }

        // 统一化：兼容 S/P/O 和 subject/predicate/object 两种格式
        var rawTriples = data.spo_triples || data.triples || [];
        var normalizedTriples = [];
        for (var t = 0; t < rawTriples.length; t++) {
            var tr = rawTriples[t];
            normalizedTriples.push({
                subject: tr.subject || tr.S || '',
                subject_type: tr.subject_type || tr.subjectType || '概念',
                predicate: tr.predicate || tr.P || '',
                relation_type: tr.relation_type || tr.relationType || tr.relation || '关联',
                object: tr.object || tr.O || '',
                object_type: tr.object_type || tr.objectType || '概念',
                context: tr.context || '',
            });
        }

        this.stats.spoTriplesExtracted += normalizedTriples.length;

        return {
            chapter: data.chapter || parseInt(chapterId),
            spo_triples: normalizedTriples,
            core_concepts: data.core_concepts || data.coreConcepts || [],
            relation_network: data.relation_network || data.relationNetwork || '',
        };
    }

    // --- 2.6 赋能方案提取 ---

    _extractEmpowerment(block) {
        var sectionMatch = block.match(EMPOWERMENT_PATTERNS.sectionHeader);
        var startIdx;

        if (sectionMatch) {
            startIdx = sectionMatch.index;
        } else {
            var looseMatch = block.search(/赋能方案/i);
            if (looseMatch < 0) return { daily_mirror: null, concept_cards: [], dq_dimensions: [] };
            startIdx = looseMatch;
        }

        var remaining = block.substring(startIdx);
        var endMatch = remaining.match(/\n(?:---|\n#{1,2}\s)/);
        var empowermentBlock = endMatch ? remaining.substring(0, endMatch.index) : remaining;

        var empowerment = {
            daily_mirror: this._parseDailyMirror(empowermentBlock),
            concept_cards: this._parseConceptCards(empowermentBlock),
            dq_dimensions: this._parseDqDimensions(empowermentBlock),
        };

        if (empowerment.daily_mirror || empowerment.concept_cards.length > 0 || empowerment.dq_dimensions.length > 0) {
            this.stats.empowermentModulesExtracted++;
        }

        return empowerment;
    }

    _parseDailyMirror(block) {
        var mirror = {};
        var wm = block.match(EMPOWERMENT_PATTERNS.dailyWisdom);
        if (wm) mirror.wisdom_quote = wm[1].trim();
        var qm = block.match(EMPOWERMENT_PATTERNS.mirrorQuestion);
        if (qm) mirror.mirror_question = qm[1].trim();
        var pm = block.match(EMPOWERMENT_PATTERNS.dailyPractice);
        if (pm) mirror.daily_practice = pm[1].trim();
        return Object.keys(mirror).length > 0 ? mirror : null;
    }

    _parseConceptCards(block) {
        var cards = [];
        var lines = block.split('\n');
        for (var i = 0; i < lines.length; i++) {
            var cardMatch = lines[i].match(/\*\*概念卡片\*\*[：:]\s*(.+)/);
            if (!cardMatch) continue;

            var cardDef = cardMatch[1].trim();
            var nameMatch = cardDef.match(/【(.+?)】/);
            var name = nameMatch ? nameMatch[1] : cardDef.substring(0, 15);

            var thoughtExp = '';
            for (var j = i + 1; j < Math.min(i + 8, lines.length); j++) {
                var teMatch = lines[j].match(/\*\*思维实验\*\*[：:]\s*(.+)/);
                if (teMatch) {
                    thoughtExp = teMatch[1].trim();
                    break;
                }
            }

            cards.push({
                name: name,
                definition: cardDef.replace(/【.+?】[：:]?\s*/, '').trim(),
                thought_experiment: thoughtExp,
            });
        }
        return cards;
    }

    _parseDqDimensions(block) {
        var dimensions = [];
        var lines = block.split('\n');
        for (var i = 0; i < lines.length; i++) {
            var dimMatch = lines[i].match(/\*\*道商维度\*\*[：:]\s*(.+)/);
            if (!dimMatch) continue;

            var dimName = dimMatch[1].trim();
            var suggestion = '';
            for (var j = i + 1; j < Math.min(i + 5, lines.length); j++) {
                var sugMatch = lines[j].match(/\*\*成长建议\*\*[：:]\s*(.+)/);
                if (sugMatch) {
                    suggestion = sugMatch[1].trim();
                    break;
                }
            }
            dimensions.push({ name: dimName, growth_suggestion: suggestion });
        }
        return dimensions;
    }

    // --- 2.7 输出生成 ---

    _generateDatabaseV2(allChapters) {
        var database = {};
        for (var i = 0; i < allChapters.length; i++) {
            var ch = allChapters[i];
            database[ch.id] = {
                chapter_title: ch.chapter_title,
                original_text: ch.original_text,
                core_concepts: ch.core_concepts,
                relation_network: ch.relation_network,
                dimensions: this._buildDimensions(ch),
                empowerment: ch.empowerment,
                spo_triples: ch.spo_triples,
                cross_references: this._extractCrossReferences(ch),
            };
        }

        var header = '// data/daojing/daojing_database_v2.js\n' +
            '// 自动生成于 ' + new Date().toISOString() + '\n' +
            '// 基于《道德经》81章五步协同读解报告\n' +
            '// 章节数: ' + Object.keys(database).length + ' | SPO三元组: ' + this.stats.spoTriplesExtracted + '\n\n' +
            'const daojingDatabaseV2 = ';

        var footer = ';\n\n' +
            '// 关键词倒排索引（自动构建）\n' +
            'const keywordIndexV2 = {};\n\n' +
            'Object.keys(daojingDatabaseV2).forEach(function(chapterId) {\n' +
            '  var chapter = daojingDatabaseV2[chapterId];\n' +
            '  if (!chapter.dimensions) return;\n' +
            '  Object.keys(chapter.dimensions).forEach(function(dimension) {\n' +
            '    [\'低\', \'高\'].forEach(function(level) {\n' +
            '      var mirrorData = chapter.dimensions[dimension] && chapter.dimensions[dimension][level];\n' +
            '      if (!mirrorData || !mirrorData.triggers) return;\n' +
            '      mirrorData.triggers.forEach(function(trigger) {\n' +
            '        if (!keywordIndexV2[trigger]) keywordIndexV2[trigger] = [];\n' +
            '        keywordIndexV2[trigger].push(chapterId + \'.\' + dimension + \'.\' + level);\n' +
            '      });\n' +
            '    });\n' +
            '  });\n' +
            '});\n\n' +
            'module.exports = { daojingDatabaseV2: daojingDatabaseV2, keywordIndexV2: keywordIndexV2 };\n';

        var output = header + JSON.stringify(database, null, 2) + footer;
        var outPath = path.join(this.outputDir, 'daojing_database_v2.js');
        fs.writeFileSync(outPath, output, 'utf-8');
        console.log('  ✓ daojing_database_v2.js (' + (output.length / 1024).toFixed(1) + ' KB)');
    }

    _buildDimensions(chapter) {
        var emp = chapter.empowerment;
        var dims = {
            '时位轴': { '低': {}, '高': {} },
            '宇位轴': { '低': {}, '高': {} },
            '识位轴': { '低': {}, '高': {} },
            '缘位轴': { '低': {}, '高': {} },
        };

        if (!emp) return dims;

        var wisdomQuote = (emp.daily_mirror && emp.daily_mirror.wisdom_quote) || '';
        var mirrorQ = (emp.daily_mirror && emp.daily_mirror.mirror_question) || '';
        var practice = (emp.daily_mirror && emp.daily_mirror.daily_practice) || '';
        var firstCard = emp.concept_cards && emp.concept_cards[0];

        // 识位轴（权重0.4）
        dims['识位轴']['高'] = {
            triggers: this._extractTriggerWords(wisdomQuote + (firstCard ? firstCard.name : '')),
            insight_desc: '镜鉴：' + wisdomQuote,
            action_desc: practice || '今日请静观自心，觉察内在智慧',
            reflection: mirrorQ || '您今天在什么时刻体验到了超越概念的直接智慧？',
        };
        dims['识位轴']['低'] = {
            triggers: ['困惑', '固执', '纠结', '迷茫', '概念'],
            insight_desc: '镜鉴：您可能陷入了固定的思维框架。' + wisdomQuote,
            action_desc: '尝试放下一个执着的观点，只是观察而不评判',
            reflection: '当您放下这个观点时，内心发生了什么变化？',
        };
        // 缘位轴（权重0.3）
        dims['缘位轴']['高'] = {
            triggers: ['包容', '倾听', '分享', '理解', '和谐'],
            insight_desc: '镜鉴：您的人际关系处于和谐流转之中，如水般柔韧包容。',
            action_desc: '今天对一位身边人说一句真诚的感谢或赞美',
            reflection: mirrorQ || '您的关系中有哪些方面可以更加"不争"？',
        };
        dims['缘位轴']['低'] = {
            triggers: ['争论', '冲突', '孤独', '对立', '说服'],
            insight_desc: '镜鉴：您可能在关系中体验到了张力，这正是"不争"的修行契机。',
            action_desc: '今天在与人的互动中，刻意练习一次"不争"——倾听而不反驳',
            reflection: '不争之后，关系的质量发生了怎样的转变？',
        };
        // 时位轴（权重0.15）
        dims['时位轴']['高'] = {
            triggers: ['耐心', '等待', '自然', '时节', '节奏'],
            insight_desc: '镜鉴：您与时间的关系和谐，能安住当下，不急于求成。',
            action_desc: practice || '今天刻意放慢一件事的节奏，感受"慢"的品质',
            reflection: '放慢之后，您对这件事的体验发生了什么变化？',
        };
        dims['时位轴']['低'] = {
            triggers: ['急躁', '焦虑', '压力', '时间不够', '紧迫'],
            insight_desc: '镜鉴：您可能感到了时间的压力。飘风不终朝，骤雨不终日。',
            action_desc: '暂停正在赶的事，做三次深长的呼吸',
            reflection: '暂停之后，您对时间的感知是否有所不同？',
        };
        // 宇位轴（权重0.15）
        dims['宇位轴']['高'] = {
            triggers: ['简单', '知足', '分享', '流动', '轻盈'],
            insight_desc: '镜鉴：您对物质的执著很轻，知足而富，空间开阔。',
            action_desc: '今天清理一件不再需要的物品，感受空间的变化',
            reflection: '放下之后，是匮乏感还是自由感？',
        };
        dims['宇位轴']['低'] = {
            triggers: ['占有', '囤积', '物质', '消费', '欲望'],
            insight_desc: '镜鉴：您可能对某种东西产生了执著。甚爱必大费，多藏必厚亡。',
            action_desc: '今天面对一个购物冲动时，停顿三分钟再做决定',
            reflection: '那三分钟的停顿中，您观察到了什么？',
        };

        return dims;
    }

    _extractTriggerWords(text) {
        var words = [];
        var raw = text.replace(/[^\u4e00-\u9fa5]/g, '');
        for (var i = 0; i < raw.length - 1; i++) {
            var bigram = raw.substring(i, i + 2);
            if (words.indexOf(bigram) < 0) words.push(bigram);
        }
        return words.slice(0, 5);
    }

    _extractCrossReferences(chapter) {
        var refs = [];
        if (chapter.original_text) {
            var matches = chapter.original_text.match(/第(\d+)章/g);
            if (matches) {
                for (var i = 0; i < matches.length; i++) {
                    var num = parseInt(matches[i].replace('第', '').replace('章', ''));
                    if (num && num !== parseInt(chapter.id) && refs.indexOf(num) < 0) {
                        refs.push(num);
                    }
                }
            }
        }
        return refs.slice(0, 5);
    }

    // --- 2.8 SPO 索引生成 ---

    _generateSpoIndex(allChapters) {
        var index = {
            generated: new Date().toISOString(),
            total_triples: this.stats.spoTriplesExtracted,
            chapter_count: allChapters.length,
            by_subject: {},
            by_relation: {},
            concept_to_chapters: {},
        };

        for (var i = 0; i < allChapters.length; i++) {
            var ch = allChapters[i];
            var triples = ch.spo_triples || [];
            for (var t = 0; t < triples.length; t++) {
                var triple = triples[t];
                var subj = triple.subject;
                if (!index.by_subject[subj]) index.by_subject[subj] = [];
                index.by_subject[subj].push({
                    chapter: ch.id,
                    predicate: triple.predicate,
                    relation_type: triple.relation_type,
                    object: triple.object,
                });

                var rel = triple.relation_type;
                if (!index.by_relation[rel]) index.by_relation[rel] = [];
                index.by_relation[rel].push({
                    chapter: ch.id,
                    subject: triple.subject,
                    predicate: triple.predicate,
                    object: triple.object,
                });
            }

            var concepts = ch.core_concepts || [];
            for (var c = 0; c < concepts.length; c++) {
                var concept = concepts[c];
                if (!index.concept_to_chapters[concept]) index.concept_to_chapters[concept] = [];
                if (index.concept_to_chapters[concept].indexOf(parseInt(ch.id)) < 0) {
                    index.concept_to_chapters[concept].push(parseInt(ch.id));
                }
            }
        }

        var output = JSON.stringify(index, null, 2);
        var outPath = path.join(this.outputDir, 'daojing_spo_index.json');
        fs.writeFileSync(outPath, output, 'utf-8');
        console.log('  ✓ daojing_spo_index.json (' + (output.length / 1024).toFixed(1) + ' KB)');
    }

    // --- 2.9 道商维度生成 ---

    _generateDqDimensions(allChapters) {
        var dimensions = {};
        var dqIndex = {};

        for (var i = 0; i < allChapters.length; i++) {
            var ch = allChapters[i];
            var dims = (ch.empowerment && ch.empowerment.dq_dimensions) || [];
            for (var d = 0; d < dims.length; d++) {
                var dim = dims[d];
                if (!dim.name) continue;
                if (!dimensions[dim.name]) {
                    dimensions[dim.name] = {
                        name: dim.name,
                        chapters: [],
                        growth_suggestions: [],
                    };
                }
                if (dimensions[dim.name].chapters.indexOf(parseInt(ch.id)) < 0) {
                    dimensions[dim.name].chapters.push(parseInt(ch.id));
                }
                if (dim.growth_suggestion) {
                    dimensions[dim.name].growth_suggestions.push({
                        chapter: ch.id,
                        suggestion: dim.growth_suggestion,
                    });
                }
                dqIndex[dim.name] = parseInt(ch.id);
            }
        }

        var header = '// data/daojing/daojing_dq_dimensions.js\n' +
            '// 自动生成于 ' + new Date().toISOString() + '\n' +
            '// 道商维度（DQ - Dao Quotient）定义库\n' +
            '// 来自81章赋能方案中的用户画像道商维度\n\n' +
            'const dqDimensions = ';

        var footer = ';\n\n' +
            'const dqChapterIndex = ' + JSON.stringify(dqIndex, null, 2) + ';\n\n' +
            'module.exports = { dqDimensions: dqDimensions, dqChapterIndex: dqChapterIndex };\n';

        var output = header + JSON.stringify(dimensions, null, 2) + footer;
        var outPath = path.join(this.outputDir, 'daojing_dq_dimensions.js');
        fs.writeFileSync(outPath, output, 'utf-8');
        console.log('  ✓ daojing_dq_dimensions.js (' + (output.length / 1024).toFixed(1) + ' KB)');
    }
}

// ============================================================
// 三、入口
// ============================================================

if (require.main === module) {
    var args = process.argv.slice(2);
    var options = {};

    for (var i = 0; i < args.length; i++) {
        if (args[i].indexOf('--reports-dir=') === 0) {
            options.reportsDir = args[i].split('=')[1];
        } else if (args[i].indexOf('--output-dir=') === 0) {
            options.outputDir = args[i].split('=')[1];
        }
    }

    var extractor = new DaojingExtractor(options);
    extractor.run().then(function (stats) {
        if (stats.errors.length > 0) process.exitCode = 1;
    }).catch(function (err) {
        console.error('提取失败:', err);
        process.exit(1);
    });
}

module.exports = DaojingExtractor;
