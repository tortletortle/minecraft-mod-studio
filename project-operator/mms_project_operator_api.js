(() => {
  "use strict";

  function createMMSProjectOperatorApi(context) {
    if (!context || typeof context.getProject !== "function" ||
        typeof context.getArchives !== "function" ||
        typeof context.getDatabase !== "function" ||
        !context.core || !context.compiler || !context.resources ||
        !context.compat || !context.migration || !context.ready) {
      throw new Error("PROJECT_OPERATOR_CONTEXT_INVALID");
    }

    const Core = context.core;
    const Compiler = context.compiler;
    const Resources = context.resources;
    const SEARCH_SCAN_LIMIT = 50000;
    const SEARCH_RESULT_BUFFER = 250;
    const INSPECT_TEXT_LIMIT = 16384;
    const INSPECT_OBJECT_LIMIT = 48000;

    const collections = project => ({
      items: project.items || [],
      blocks: project.studio?.blocks || [],
      mobs: project.studio?.mobs || [],
      quests: project.studio?.quests || [],
      effects: project.studio?.effects || [],
      guis: project.studio?.guis || []
    });

    const clone = value => JSON.parse(JSON.stringify(value));
    const sourceFor = (archive, entry) => ({
      archive: String(archive.name || "").slice(0, 80),
      archiveId: archive.id,
      path: String(entry.path || "").slice(0, 256),
      modId: archive.meta?.id || "",
      loader: archive.meta?.loader || "unknown",
      version: String(archive.meta?.version || "").slice(0, 40),
      license: String(archive.meta?.license || "未知").slice(0, 80),
      licenseClaimsUnverified: true
    });

    async function snapshot() {
      await context.ready;
      const project = context.getProject();
      const archives = context.getArchives();
      const validation = Core.validate(project);
      const build = Compiler.analyze(project);
      let revision = null;
      let revisionStatus = "unavailable";
      try {
        const canonical = Core.encode(project);
        const digest = await crypto.subtle.digest(
          "SHA-256", new TextEncoder().encode(canonical)
        );
        revision = Array.from(
          new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")
        ).join("");
        revisionStatus = "sha256_of_studiocore_encode";
      } catch (error) {
        revisionStatus = "unavailable:" + String(error.message || error).slice(0, 160);
      }

      const groups = collections(project);
      const overrides = project.resourceOverrides || [];
      return {
        schemaVersion: project.schemaVersion,
        project: {
          name: project.name,
          modId: project.modId,
          target: project.target || {}
        },
        revision,
        revisionStatus,
        counts: {
          items: groups.items.length,
          blocks: groups.blocks.length,
          mobs: groups.mobs.length,
          quests: groups.quests.length,
          effects: groups.effects.length,
          guis: groups.guis.length,
          stagedResourceOverrides: overrides.length,
          importedArchives: archives.length,
          importedResources: archives.reduce(
            (count, archive) => count + (Array.isArray(archive.entries) ? archive.entries.length : 0), 0
          )
        },
        stagedResourceOverrides: overrides.slice(0, 10).map(record => ({
          path: String(record.path || "").slice(0, 256),
          replace: record.replace === true,
          dependency: String(record.dependency || "").slice(0, 160),
          source: {
            archive: String(record.source?.archive || "").slice(0, 80),
            path: String(record.source?.path || "").slice(0, 256),
            modId: record.source?.modId || "",
            loader: record.source?.loader || "unknown",
            version: String(record.source?.version || "").slice(0, 40),
            license: String(record.source?.license || "未知").slice(0, 80)
          },
          sourceMetadataUnverified: true
        })),
        stagedOverridesTruncated: overrides.length > 10,
        importedArchives: archives.map(archive => ({
          id: archive.id,
          name: String(archive.name || "").slice(0, 80),
          modId: archive.meta?.id || "",
          loader: archive.meta?.loader || "unknown",
          version: String(archive.meta?.version || "").slice(0, 40),
          license: String(archive.meta?.license || "未知").slice(0, 80),
          entries: Array.isArray(archive.entries) ? archive.entries.length : 0,
          totalBytes: Number(archive.total) || 0,
          skipped: Number(archive.skipped) || 0,
          licenseFileCount: Array.isArray(archive.licenses) ? archive.licenses.length : 0,
          archiveMetadataUnverified: true
        })),
        validation: {
          errors: (validation.errors || []).slice(0, 10).map(value => String(value).slice(0, 160)),
          warnings: (validation.warnings || []).slice(0, 10).map(value => String(value).slice(0, 160)),
          truncated: (validation.errors || []).length > 10 || (validation.warnings || []).length > 10
        },
        buildAnalysis: {
          errors: (build.errors || []).slice(0, 10).map(value => String(value).slice(0, 160)),
          warnings: (build.warnings || []).slice(0, 10).map(value => String(value).slice(0, 160)),
          omitted: (build.omitted || []).slice(0, 10).map(value => String(value).slice(0, 160)),
          truncated: (build.errors || []).length > 10 ||
            (build.warnings || []).length > 10 || (build.omitted || []).length > 10
        },
        resourceLibrary: {
          indexedDbAvailable: !!context.getDatabase(),
          archiveCount: archives.length
        },
        trust: {
          importedResourceContent: "untrusted_mod_supplied_data",
          archiveMetadata: "unverified_claims",
          projectData: "user_project_data"
        }
      };
    }

    function compareSearchRows(a, b) {
      return b.score - a.score ||
        String(a.path || a.id || "").localeCompare(String(b.path || b.id || ""));
    }

    function searchSync(args = {}) {
      const project = context.getProject();
      const archives = context.getArchives();
      const query = typeof args.query === "string" ? args.query.trim().toLowerCase() : "";
      const scope = args.scope || "all";
      const archiveId = args.archiveId || "";
      const kind = args.kind || "";
      const limit = args.limit === undefined ? 20 : args.limit;

      if (!query || query.length > 160) throw new Error("搜索词必须为 1–160 个字符");
      if (!["all", "project", "resources"].includes(scope)) throw new Error("无效搜索范围");
      if (typeof archiveId !== "string" || archiveId.length > 64 ||
          typeof kind !== "string" || kind.length > 32) throw new Error("筛选条件无效");
      if (!Number.isInteger(limit) || limit < 1 || limit > 50) {
        throw new Error("结果数量必须为 1–50");
      }

      const terms = [...new Set(query.split(/\s+/).filter(Boolean))];
      const rows = [];
      let totalMatches = 0;
      const add = (score, matchedFields, row) => {
        if (score <= 0) return;
        totalMatches += 1;
        const candidate = { ...row, score, matchedFields };
        let low = 0;
        let high = rows.length;
        while (low < high) {
          const middle = (low + high) >> 1;
          if (compareSearchRows(candidate, rows[middle]) < 0) high = middle;
          else low = middle + 1;
        }
        if (low < SEARCH_RESULT_BUFFER || rows.length < SEARCH_RESULT_BUFFER) {
          rows.splice(low, 0, candidate);
          if (rows.length > SEARCH_RESULT_BUFFER) rows.pop();
        }
      };

      if (scope === "all" || scope === "project") {
        for (const [collection, list] of Object.entries(collections(project))) {
          for (const item of list) {
            const fields = {
              id: String(item.id || ""),
              name: String(item.name || ""),
              collection,
              kind: String(item.kind || item.type || ""),
              details: [item.ai, item.body, item.category, item.description, item.material]
                .filter(value => typeof value === "string").join(" ")
            };
            const matched = terms.filter(term =>
              Object.values(fields).some(value => value.toLowerCase().includes(term))
            );
            if (matched.length !== terms.length) continue;
            let score = matched.length * 2;
            if (fields.id.toLowerCase() === query) score += 12;
            if (fields.name.toLowerCase().includes(query)) score += 8;
            add(
              score,
              Object.entries(fields)
                .filter(([, value]) => terms.some(term => value.toLowerCase().includes(term)))
                .map(([key]) => key),
              {
                resultType: "project_object",
                collection,
                id: fields.id,
                name: fields.name,
                kind: fields.kind
              }
            );
          }
        }
      }

      let scanned = 0;
      if (scope === "all" || scope === "resources") {
        for (const archive of archives) {
          if (archiveId && archive.id !== archiveId) continue;
          for (const entry of archive.entries || []) {
            if (scanned >= SEARCH_SCAN_LIMIT) break;
            scanned += 1;
            const resourceKind = Resources.kind(entry.path);
            if (kind && resourceKind !== kind) continue;
            const fields = {
              path: String(entry.path),
              archive: String(archive.name || ""),
              modId: String(archive.meta?.id || ""),
              version: String(archive.meta?.version || ""),
              loader: String(archive.meta?.loader || ""),
              kind: resourceKind
            };
            const matched = terms.filter(term =>
              Object.values(fields).some(value => value.toLowerCase().includes(term))
            );
            if (matched.length !== terms.length) continue;
            let score = matched.length * 2;
            if (fields.path.toLowerCase() === query) score += 16;
            if (fields.path.toLowerCase().includes(query)) score += 8;
            if (fields.modId.toLowerCase() === query) score += 10;
            add(
              score,
              Object.entries(fields)
                .filter(([, value]) => terms.some(term => value.toLowerCase().includes(term)))
                .map(([key]) => key),
              {
                resultType: "imported_resource",
                archiveId: archive.id,
                path: entry.path,
                kind: resourceKind,
                size: entry.bytes?.length || 0,
                source: sourceFor(archive, entry),
                sourceMetadataUnverified: true
              }
            );
          }
          if (scanned >= SEARCH_SCAN_LIMIT) break;
        }

        if (!archiveId || archiveId === "project") {
          for (const record of project.resourceOverrides || []) {
            if (kind && Resources.kind(record.path) !== kind) continue;
          const fields = {
            path: String(record.path),
            archive: String(record.source?.archive || ""),
            modId: String(record.source?.modId || ""),
            license: String(record.source?.license || "")
          };
          const matched = terms.filter(term =>
            Object.values(fields).some(value => value.toLowerCase().includes(term))
          );
          if (matched.length !== terms.length) continue;
          add(
            matched.length * 2 + 8,
            Object.entries(fields)
              .filter(([, value]) => terms.some(term => value.toLowerCase().includes(term)))
              .map(([key]) => key),
            {
              resultType: "staged_project_resource",
              archiveId: "project",
              path: record.path,
              kind: Resources.kind(record.path),
              size: Math.floor(String(record.base64 || "").length * 3 / 4),
              source: clone(record.source || {}),
              sourceMetadataUnverified: true
            }
          );
          }
        }
      }

      return {
        query,
        scope,
        results: rows.slice(0, limit),
        resultCount: Math.min(rows.length, limit),
        totalMatches,
        scanLimit: SEARCH_SCAN_LIMIT,
        scannedResources: scanned,
        scanTruncated: (scope === "all" || scope === "resources") &&
          archives.filter(archive => !archiveId || archive.id === archiveId)
            .reduce((count, archive) => count + (archive.entries?.length || 0), 0) > SEARCH_SCAN_LIMIT
      };
    }

    function inspectResourceSync(args = {}) {
      const project = context.getProject();
      const archives = context.getArchives();
      const archiveId = args.archiveId;
      const path = args.path;
      if (typeof archiveId !== "string" || archiveId.length > 64 ||
          typeof path !== "string" || path.length > 512) {
        throw new Error("资源定位参数无效");
      }

      let bytes;
      let source;
      if (archiveId === "project") {
        const record = (project.resourceOverrides || []).find(item => item.path === path);
        if (!record) throw new Error("找不到项目补丁资源：" + path);
        bytes = Resources.un64(record.base64);
        source = clone(record.source || {});
      } else {
        const archive = archives.find(item => item.id === archiveId);
        if (!archive) throw new Error("找不到导入来源：" + archiveId);
        const entry = (archive.entries || []).find(item => item.path === path);
        if (!entry) throw new Error("找不到资源路径：" + path);
        bytes = entry.bytes;
        source = sourceFor(archive, entry);
      }

      const resourceKind = Resources.kind(path);
      const isText = /\.(json|mcmeta|jem|jpm|bbmodel)$/.test(path);
      const result = {
        archiveId,
        path,
        kind: resourceKind,
        size: bytes.length,
        crc32: Resources.crc(bytes).toString(16).padStart(8, "0"),
        source,
        sourceMetadataUnverified: true,
        references: [],
        contentTrust: "untrusted_mod_supplied_data"
      };
      try {
        const references = Resources.refs(path, bytes);
        result.references = references.slice(0, 64).map(value => String(value).slice(0, 256));
        result.referencesTruncated = references.length > 64;
      } catch (error) {
        result.referenceError = String(error.message || error).slice(0, 160);
      }
      if (isText && bytes.length <= INSPECT_TEXT_LIMIT) {
        try {
          result.content = Resources.decode(bytes);
        } catch (error) {
          result.contentUnavailable = String(error.message || error).slice(0, 160);
        }
      } else if (isText) {
        result.contentTruncated = true;
        result.contentLimitBytes = INSPECT_TEXT_LIMIT;
      } else {
        result.binaryContentOmitted = true;
      }
      return result;
    }

    const sourceSummary = source => ({
      archive: String(source?.archive || "").slice(0, 80),
      path: String(source?.path || "").slice(0, 256),
      modId: String(source?.modId || "").slice(0, 64),
      loader: String(source?.loader || "unknown").slice(0, 32),
      version: String(source?.version || "").slice(0, 40),
      license: String(source?.license || "未知").slice(0, 80),
      sourceMetadataUnverified: true
    });

    async function analyzeCompatibility() {
      await context.ready;
      const project = context.getProject();
      const archives = context.getArchives();
      const analysis = context.compat.analyze(archives, project);
      const candidates = (analysis.candidates || []).slice(0, 10).map(candidate => {
        const beforeBytes = new TextEncoder().encode(JSON.stringify(candidate.before));
        const afterBytes = new TextEncoder().encode(JSON.stringify(candidate.after));
        return {
          path: candidate.path,
          changes: (candidate.changes || []).slice(0, 8),
          source: sourceSummary(candidate.source),
          dependencies: (candidate.dependencies || []).slice(0, 16),
          evidence: (candidate.evidence || []).slice(0, 16),
          beforeBytes: beforeBytes.length,
          afterBytes: afterBytes.length,
          beforeCrc32: Resources.crc(beforeBytes).toString(16).padStart(8, "0"),
          afterCrc32: Resources.crc(afterBytes).toString(16).padStart(8, "0"),
          fullRecipeContentOmitted: true
        };
      });
      const groups = (analysis.groups || []).slice(0, 6).map(group => ({
        tag: group.tag,
        memberCount: (group.members || []).length,
        members: (group.members || []).slice(0, 8).map(member => ({
          item: String(member.item || "").slice(0, 128),
          declaredBy: (member.declaredBy || []).slice(0, 4).map(value => String(value).slice(0, 64)),
          declaredByTruncated: (member.declaredBy || []).length > 4
        })),
        membersTruncated: (group.members || []).length > 8,
        dependencies: (group.dependencies || []).slice(0, 16),
        sources: (group.sources || []).slice(0, 4).map(sourceSummary),
        sourcesTruncated: (group.sources || []).length > 4
      }));
      const ambiguous = (analysis.ambiguous || []).slice(0, 20).map(item => ({
        path: item.path,
        item: item.item,
        tags: (item.tags || []).slice(0, 8),
        tagsTruncated: (item.tags || []).length > 8
      }));
      const collisions = (analysis.collisions || []).slice(0, 10).map(item => ({
        path: item.path,
        sources: (item.sources || []).slice(0, 4),
        sourcesTruncated: (item.sources || []).length > 4,
        mergeableTag: item.mergeableTag === true
      }));
      return {
        mode: "read_only_compatibility_analysis",
        stats: analysis.stats || {},
        groups,
        candidates,
        ambiguous,
        collisions,
        edges: (analysis.edges || []).slice(0, 20),
        warnings: (analysis.warnings || []).slice(0, 20).map(value => String(value).slice(0, 160)),
        truncated: {
          groups: (analysis.groups || []).length > 6,
          candidates: (analysis.candidates || []).length > 10,
          ambiguous: (analysis.ambiguous || []).length > 20,
          collisions: (analysis.collisions || []).length > 10,
          edges: (analysis.edges || []).length > 20,
          warnings: (analysis.warnings || []).length > 20
        },
        sourceMetadataUnverified: true,
        projectMutated: false,
        patchesStaged: false
      };
    }

    async function planMigration(args = {}) {
      await context.ready;
      const project = context.getProject();
      const archives = context.getArchives();
      const rootPath = args.rootPath;
      const bindItem = args.bindItem || "";
      if (typeof rootPath !== "string" || !rootPath || rootPath.length > 512) {
        throw new Error("迁移根资源路径必须为 1–512 个字符");
      }
      if (typeof bindItem !== "string" || bindItem.length > 80) {
        throw new Error("绑定物品 ID 无效");
      }
      const plan = context.migration.plan(archives, project, rootPath, { bindItem });
      const rows = (plan.rows || []).slice(0, 10).map(row => ({
        from: row.from,
        to: row.to,
        source: sourceSummary(row.source),
        size: row.bytes?.length || 0,
        crc32: Resources.crc(row.bytes).toString(16).padStart(8, "0"),
        replace: row.replace === true
      }));
      let projectRevision = null;
      try {
        const canonical = Core.encode(project);
        const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical));
        projectRevision = Array.from(
          new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")
        ).join("");
      } catch (_) {}
      const planManifest = {
        projectRevision,
        rootPath,
        bindItem,
        rows: (plan.rows || []).map(row => ({
          from: row.from,
          to: row.to,
          size: row.bytes?.length || 0,
          crc32: Resources.crc(row.bytes).toString(16).padStart(8, "0"),
          source: sourceSummary(row.source)
        })),
        errors: plan.errors || []
      };
      let planId = null;
      try {
        const digest = await crypto.subtle.digest(
          "SHA-256", new TextEncoder().encode(JSON.stringify(planManifest))
        );
        planId = Array.from(
          new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")
        ).join("");
      } catch (_) {}
      return {
        mode: "read_only_migration_plan",
        status: (plan.errors || []).length ? "blocked" : (plan.rows || []).length ? "candidate_plan_only" : "no_resources",
        planId,
        projectRevision,
        root: plan.root,
        namespace: plan.namespace,
        bindItem: plan.bindItem,
        rowCount: (plan.rows || []).length,
        rows,
        rowsTruncated: (plan.rows || []).length > 10,
        edgeCount: (plan.edges || []).length,
        edges: (plan.edges || []).slice(0, 10),
        edgesTruncated: (plan.edges || []).length > 10,
        externals: (plan.externals || []).slice(0, 5),
        externalsTruncated: (plan.externals || []).length > 5,
        errors: (plan.errors || []).slice(0, 10).map(value => String(value).slice(0, 160)),
        errorsTruncated: (plan.errors || []).length > 10,
        totalBytes: plan.total || 0,
        sourceMetadataUnverified: true,
        projectMutated: false,
        patchesStaged: false,
        applyAvailable: false
      };
    }

    function inspectProjectObjectSync(args = {}) {
      const project = context.getProject();
      const groups = collections(project);
      const collection = args.collection;
      const id = args.id;
      if (typeof collection !== "string" ||
          !Object.prototype.hasOwnProperty.call(groups, collection) ||
          typeof id !== "string" || id.length > 80) {
        throw new Error("项目对象定位参数无效");
      }
      const item = groups[collection].find(value => value.id === id || value.uid === id);
      if (!item) throw new Error("找不到项目对象：" + collection + "/" + id);
      const copy = clone(item);
      let detailsTruncated = false;
      if (new TextEncoder().encode(JSON.stringify(copy)).length > INSPECT_OBJECT_LIMIT) {
        detailsTruncated = true;
        if (copy.model && typeof copy.model === "object") {
          copy.model = {
            boneCount: Array.isArray(copy.model.bones) ? copy.model.bones.length : 0,
            animationCount: Array.isArray(copy.model.animations) ? copy.model.animations.length : 0,
            detailOmitted: true
          };
        }
        if (Array.isArray(copy.pixels)) {
          copy.pixels = {
            pixelCount: copy.pixels.length,
            nonTransparent: copy.pixels.filter(Boolean).length,
            detailOmitted: true
          };
        }
        for (const key of ["graph", "behaviorTree", "animationStateMachine"]) {
          if (copy[key] && typeof copy[key] === "object") {
            copy[key] = { detailOmitted: true };
          }
        }
      }
      if (new TextEncoder().encode(JSON.stringify(copy)).length > INSPECT_OBJECT_LIMIT) {
        throw new Error("项目对象超出只读检查大小上限；请先检查更小的资源或字段");
      }
      return {
        collection,
        id,
        object: copy,
        detailsTruncated,
        projectRevisionHint: "Call mms_project_snapshot for the current SHA-256 revision."
      };
    }

    return Object.freeze({
      snapshot,
      search: async args => {
        await context.ready;
        return searchSync(args);
      },
      inspectResource: async args => {
        await context.ready;
        return inspectResourceSync(args);
      },
      inspectProjectObject: async args => {
        await context.ready;
        return inspectProjectObjectSync(args);
      },
      analyzeCompatibility,
      planMigration
    });
  }

  window.MMSProjectOperatorFactory = createMMSProjectOperatorApi;
})();