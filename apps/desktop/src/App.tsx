import { useState } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { AnimatePresence, motion } from "framer-motion";
import { TitleBar } from "./components/TitleBar";
import { HistoryPanel } from "./components/HistoryPanel";
import { CanvasPanel } from "./components/CanvasPanel";
import { InspectorPanel } from "./components/InspectorPanel";
import { CompanionDownloadModal } from "./components/CompanionDownloadModal";
import { InpaintMaskModal } from "./components/InpaintMaskModal";
import { FullLogModal } from "./components/FullLogModal";
import { ReliabilityBanner } from "./components/ReliabilityBanner";
import { useDreamForge } from "./hooks/useDreamForge";

export default function App() {
  const mc = useDreamForge();
  const [fullLogOpen, setFullLogOpen] = useState(false);

  return (
    <>
      <div className="app-backdrop" aria-hidden />
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="app-shell"
      >
      <TitleBar
        engineState={mc.engineState}
        bootMessage={mc.bootMessage}
        gpuName={mc.gpuName}
        vramGb={mc.vramGb}
        mpsAvailable={mc.mpsAvailable}
      />
      <ReliabilityBanner
        lastError={mc.lastError}
        warnings={mc.warnings}
        onDismissError={mc.dismissLastError}
        onDismissWarning={mc.dismissWarning}
        onDismissAllWarnings={mc.dismissAllWarnings}
        onRestartEngine={() => void mc.runRestartEngine()}
        onDownloadCompanions={() => void mc.downloadMissingCompanions()}
        onLowerVramProfile={mc.lowerVramProfile}
        companionDownloadBusy={mc.companionDownloadBusy}
        restarting={mc.restarting}
      />
      <AnimatePresence mode="wait">
        {mc.status && (
          <motion.div
            key={mc.status}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.2 }}
            className="flex items-center justify-center gap-2 px-3 pb-1"
          >
            <div className="h-1 w-1 rounded-full bg-dfui-data/50" />
            <p className="text-center font-mono text-[11px] text-dfui-secondary tracking-wide">{mc.status}</p>
            <div className="h-1 w-1 rounded-full bg-dfui-forge/50" />
          </motion.div>
        )}
      </AnimatePresence>
      <PanelGroup direction="horizontal" className="min-h-0 flex-1">
        <Panel defaultSize={22} minSize={16} maxSize={35}>
          <HistoryPanel
            sessions={mc.sessions}
            activeSessionId={mc.activeSessionId}
            onSwitchSession={(id) => mc.switchSession(id, { previewFirst: true })}
            onCreateSession={(name) => mc.createSession(name)}
            selected={mc.selected}
            onSelect={mc.setSelected}
            onRefresh={() => void mc.refreshOutputs()}
            onLoadMore={
              mc.outputsHasMore ? () => mc.loadMoreOutputs() : undefined
            }
            outputsTotal={mc.outputsTotal}
            outputsLoaded={mc.outputsLoaded}
            loadingOutputs={mc.outputsLoading}
            outputSearch={mc.outputSearch}
            onOutputSearchChange={mc.setOutputSearch}
            onReusePrompt={mc.reuseOutputPrompt}
            onOpenFolder={(path) => void mc.openOutputInExplorer(path)}
            onCopyPath={(path) => void mc.copyOutputPath(path)}
            onDeleteGeneration={(item) => void mc.deleteOutputManifest(item)}
            onDeleteImage={(item, path) =>
              void mc.deleteOutputImageFile(item, path)
            }
            onDeleteSession={(session) => void mc.deleteOutputSession(session)}
            historyScrollToken={mc.historyScrollToken}
            onLibrarySelect={(path) => {
              mc.attachReferenceImage(path, "reference");
              void mc.selectGalleryImage(path);
            }}
          />
        </Panel>
        <PanelResizeHandle className="w-1 bg-dfui-border/50 transition hover:bg-dfui-accent/60" />
        <Panel defaultSize={50} minSize={35}>
          <CanvasPanel
            previewUrl={mc.previewUrl}
            liveProgress={mc.liveProgress}
            workerReady={mc.workerReady}
            canGenerate={mc.canGenerate}
            generateBlockReason={mc.generateBlockReason}
            needsCompanionDownload={mc.needsCompanionDownload}
            missingCompanionCount={mc.missingDownloadCount}
            companionDownloadBusy={mc.companionDownloadBusy}
            onDownloadCompanions={() => void mc.downloadMissingCompanions()}
            engineState={mc.engineState}
            bootMessage={mc.bootMessage}
            workerLogTail={mc.workerLogTail}
            restarting={mc.restarting}
            onRestartEngine={() => void mc.runRestartEngine()}
            selected={mc.selected}
            studioMode={mc.studioMode}
            agentPlannedMode={mc.agentPlannedMode}
            onStudioModeChange={(mode) => void mc.setStudioMode(mode)}
            settings={mc.settings}
            onChange={mc.patchSettings}
            mentions={mc.mentionTargets}
            generating={mc.generating}
            generationLog={mc.generationLog}
            agentPlan={mc.agentPlan}
            planApprovalRequired={mc.appConfig?.agent.approval_required}
            planRunBusy={mc.planRunBusy}
            onApplyAgentPlan={() => void mc.applyAgentPlan()}
            onRunApprovedPlan={() => void mc.runApprovedPlan()}
            onDismissAgentPlan={mc.dismissAgentPlan}
            onDryRun={() => void mc.runDryRun()}
            onGenerate={() => void mc.runGenerate()}
            onCancel={() => void mc.runCancel()}
            onUseSelectedImageFor={mc.useSelectedImageFor}
            onAttachReferenceImage={mc.attachReferenceImage}
            onAttachExtraReferenceImage={(path) =>
              void mc.attachExtraReferenceImage(path)
            }
            onRemoveExtraReferenceImage={mc.removeExtraReferenceImage}
            onClearReferenceImage={mc.clearReferenceImage}
            onOpenInpaintMask={() => mc.setInpaintMaskOpen(true)}
            onOpenFullLog={() => setFullLogOpen(true)}
            activeModelLabel={mc.activeModelLabel}
          />
        </Panel>
        <PanelResizeHandle className="w-1 bg-dfui-border/50 transition hover:bg-dfui-accent/60" />
        <Panel defaultSize={28} minSize={22} maxSize={40}>
          <InspectorPanel
            settings={mc.settings}
            onChange={mc.patchSettings}
            modelGallery={mc.modelGallery}
            loraGallery={mc.loraGallery}
            modelFilter={mc.modelFilter}
            onModelFilterChange={mc.setModelFilter}
            loraFilter={mc.loraFilter}
            onLoraFilterChange={mc.setLoraFilter}
            lockFamilyDefaults={mc.lockFamilyDefaults}
            onLockFamilyDefaultsChange={mc.setLockFamilyDefaults}
            profileHints={mc.profileHints}
            galleryLoading={mc.galleryLoading}
            onSelectModel={(item) => void mc.selectModelGallery(item)}
            onToggleLora={mc.toggleLoraGallery}
            styleGroups={mc.inventory.styleGroups}
            aspectPresets={mc.aspectPresets}
            uiDefaults={mc.uiDefaults}
            activeModelLabel={mc.activeModelLabel}
            studioMode={mc.studioMode}
            onUseCaseChange={mc.setUseCase}
            onRefreshInventory={mc.refreshStudioCatalog}
            modelDependencies={mc.modelDependencies}
            companionDownloadBusy={mc.companionDownloadBusy}
            onDownloadCompanions={() => void mc.downloadMissingCompanions()}
            onRefreshModelDependencies={() => void mc.refreshModelDependencies()}
            studioSettings={mc.studioSettings}
            onSaveStudioSettings={(patch) => void mc.saveStudioSettings(patch)}
            appConfig={mc.appConfig}
            agentProviders={mc.agentProviders}
            agentProviderTest={mc.agentProviderTest}
            agentProviderBusy={mc.agentProviderBusy}
            onSaveAppConfig={(patch) => void mc.saveAppConfig(patch)}
            onTestAgentProvider={(patch) => void mc.testAgentProvider(patch)}
            imageNumberMax={mc.imageNumberMax}
            userStyleProfile={mc.userStyleProfile}
            userStyleProfilePath={mc.userStyleProfilePath}
            onUserStyleMemoryEnabledChange={(enabled) =>
              void mc.setUserStyleMemoryEnabled(enabled)
            }
            onClearUserStyleMemory={() => void mc.clearUserStyleMemory()}
            onExportUserStyleMemory={() => void mc.exportUserStyleMemory()}
          />
        </Panel>
      </PanelGroup>
    </motion.div>
      <FullLogModal
        open={fullLogOpen}
        jobId={mc.logJobId}
        onClose={() => setFullLogOpen(false)}
      />
      <InpaintMaskModal
        open={mc.inpaintMaskOpen}
        imagePath={mc.settings.input_image ?? ""}
        onClose={() => mc.setInpaintMaskOpen(false)}
        onSave={(path) => {
          mc.setInpaintMaskPath(path);
          mc.setInpaintMaskOpen(false);
        }}
      />
      <CompanionDownloadModal
        open={mc.companionDownload.open}
        phase={mc.companionDownload.phase}
        lines={mc.companionDownload.lines}
        currentIndex={mc.companionDownload.currentIndex}
        totalCount={mc.companionDownload.totalCount}
        currentItem={mc.companionDownload.currentItem}
        fileProgress={mc.companionDownload.fileProgress}
        modelName={mc.companionDownload.modelName}
        pendingMissing={mc.companionDownload.pendingMissing}
        onClose={mc.companionDownload.close}
        onApprove={mc.companionDownload.approve}
        onRetry={mc.companionDownload.retry}
      />
    </>
  );
}
