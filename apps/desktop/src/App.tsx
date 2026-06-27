import { useState, useEffect } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { TitleBar } from "./components/TitleBar";
import { HistoryPanel } from "./components/HistoryPanel";
import { CanvasPanel } from "./components/CanvasPanel";
import { InspectorPanel } from "./components/InspectorPanel";
import { CompanionDownloadModal } from "./components/CompanionDownloadModal";
import { InpaintMaskModal } from "./components/InpaintMaskModal";
import { FullLogModal } from "./components/FullLogModal";
import { AppSettingsModal } from "./components/AppSettingsModal";
import { SetupWizard } from "./components/SetupWizard";
import { ReliabilityBanner } from "./components/ReliabilityBanner";
import { useDreamForge } from "./hooks/useDreamForge";
import { shouldHideGlobalStatusForProgress } from "./lib/studioProgress";
import { getSetupGateStatus } from "./lib/runtimeSetup";

export default function App() {
  const [setupComplete, setSetupComplete] = useState<boolean | null>(null);

  useEffect(() => {
    void getSetupGateStatus()
      .then((gate) => setSetupComplete(gate.setup_complete))
      .catch(() => setSetupComplete(false));
  }, []);

  if (setupComplete === null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-dfui-bg text-dfui-muted">
        <Loader2 className="h-6 w-6 animate-spin text-dfui-accent" />
      </div>
    );
  }

  if (!setupComplete) {
    return <SetupWizard onComplete={() => setSetupComplete(true)} />;
  }

  return <DreamForgeStudio />;
}

function DreamForgeStudio() {
  const mc = useDreamForge();
  const [fullLogOpen, setFullLogOpen] = useState(false);
  const [appSettingsOpen, setAppSettingsOpen] = useState(false);
  const hideGlobalStatus = shouldHideGlobalStatusForProgress({
    engineState: mc.engineState,
    generating: mc.generating,
    companionBootstrapBusy: mc.companionBootstrapBusy,
  });

  const profileLabel = "Local profile";
  const profileDetail = mc.userStyleProfile
    ? `${mc.userStyleProfile.generation_count ?? 0} remembered jobs${
        mc.userStyleProfile.favorite_models?.[0]
          ? ` · ${mc.userStyleProfile.favorite_models[0]}`
          : ""
      }`
    : undefined;

  return (
    <>
      <div className="app-backdrop" aria-hidden />
      <div className="app-shell animate-fade-in">
      <TitleBar
        engineState={mc.engineState}
        bootMessage={mc.bootMessage}
        gpuName={mc.gpuName}
        vramGb={mc.vramGb}
        mpsAvailable={mc.mpsAvailable}
        profileLabel={profileLabel}
        profileDetail={profileDetail}
        experience={mc.uiExperience}
        onExperienceChange={(exp) =>
          void mc.saveAppConfig({
            ui: { experience: exp, advanced_mode: exp === "pro" },
          })
        }
        onOpenAppSettings={() => setAppSettingsOpen(true)}
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
        {mc.status && !hideGlobalStatus && (
          <motion.div
            key={mc.status}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.2 }}
            className="flex shrink-0 items-center justify-center gap-2 px-3 pb-1"
          >
            <div className="h-1 w-1 rounded-full bg-dfui-data/50" />
            <p className="text-center font-mono text-[11px] text-dfui-secondary tracking-wide">{mc.status}</p>
            <div className="h-1 w-1 rounded-full bg-dfui-forge/50" />
          </motion.div>
        )}
      </AnimatePresence>
      <PanelGroup direction="horizontal" className="min-h-0 flex-1 overflow-hidden">
        <Panel defaultSize={18} minSize={14} maxSize={30} className="min-h-0">
          <div className="df-panel-shell">
          <HistoryPanel
            sessions={mc.sessions}
            activeSessionId={mc.activeSessionId}
            onSaveSessionChange={(id) => mc.switchSession(id)}
            onCreateSession={(name) => mc.createSession(name)}
            selected={mc.selected}
            onSelect={mc.setSelected}
            onRefresh={() => void mc.refreshOutputs({ keepSelection: true })}
            onLoadMore={
              mc.outputsHasMore ? () => mc.loadMoreOutputs() : undefined
            }
            outputsTotal={mc.outputsTotal}
            outputsLoaded={mc.outputsLoaded}
            loadingOutputs={mc.outputsLoading}
            outputSearch={mc.outputSearch}
            onOutputSearchChange={mc.setOutputSearch}
            onReusePrompt={(item) => void mc.reuseOutputPrompt(item)}
            onEditThis={(item) => void mc.historyEditThis(item)}
            onFixRegion={(item) => void mc.historyFixRegion(item)}
            onEnhance={(item) => void mc.historyEnhance(item)}
            simpleHistoryLabels={mc.uiExperience === "simple"}
            onOpenFolder={(path) => void mc.openOutputInExplorer(path)}
            onCopyPath={(path) => void mc.copyOutputPath(path)}
            onDeleteGeneration={(item) => void mc.deleteOutputManifest(item)}
            onDeleteImage={(item, path) =>
              void mc.deleteOutputImageFile(item, path)
            }
            onDeleteSession={(session) => void mc.deleteOutputSession(session)}
            historyScrollToken={mc.historyScrollToken}
          />
          </div>
        </Panel>
        <PanelResizeHandle className="w-1 bg-dfui-border/50 transition hover:bg-dfui-accent/60" />
        <Panel defaultSize={58} minSize={42} className="min-h-0">
          <div className="df-panel-shell">
          <CanvasPanel
            previewUrl={mc.previewUrl}
            liveProgress={mc.liveProgress}
            workerReady={mc.workerReady}
            canGenerate={mc.canGenerate}
            companionBlockedOnly={mc.companionBlockedOnly}
            generateBlockReason={mc.generateBlockReason}
            needsCompanionDownload={mc.needsCompanionDownload}
            missingCompanionCount={mc.missingDownloadCount}
            companionDownloadBusy={mc.companionDownloadBusy}
            onDownloadCompanions={() => void mc.downloadMissingCompanions()}
            engineState={mc.engineState}
            bootMessage={mc.bootMessage}
            bootPhase={mc.bootPhase}
            workerLogTail={mc.workerLogTail}
            restarting={mc.restarting}
            onRestartEngine={() => void mc.runRestartEngine()}
            companionBootstrapBusy={mc.companionBootstrapBusy}
            companionBootstrapMessage={mc.companionBootstrapMessage}
            studioMode={mc.studioMode}
            agentPlannedMode={mc.agentPlannedMode}
            onStudioModeChange={(mode) => void mc.setStudioMode(mode)}
            experience={mc.uiExperience}
            settings={mc.settings}
            onChange={mc.patchSettings}
            mentions={mc.mentionTargets}
            generating={mc.generating}
            generationLog={mc.generationLog}
            agentPlan={mc.agentPlan}
            agentTranscript={mc.agentTranscript}
            agentRuntimeLabel={mc.agentRuntimeLabel}
            planApprovalRequired={mc.appConfig?.agent.approval_required}
            planRunBusy={mc.planRunBusy}
            onApplyAgentPlan={() => void mc.applyAgentPlan()}
            onRunApprovedPlan={() => void mc.runApprovedPlan()}
            onDismissAgentPlan={mc.dismissAgentPlan}
            onClearAgentTranscript={mc.clearAgentTranscript}
            onDryRun={() => void mc.runDryRun()}
            onEnhancePrompt={() => void mc.runEnhancePrompt()}
            enhancePromptBusy={mc.enhancePromptBusy}
            onDescribeImage={() => void mc.runDescribeImage()}
            describeImageBusy={mc.describeImageBusy}
            describeImagePath={mc.describeImagePath}
            onImportImageMetadata={(path) => void mc.runImportImageMetadata(path)}
            onGenerate={() => void mc.runGenerate()}
            onGenerateVariants={(count) => void mc.runGenerateVariants(count)}
            imageNumberMax={mc.imageNumberMax}
            onCancel={() => void mc.runCancel()}
            onAttachReferenceImage={mc.attachReferenceImage}
            onAttachExtraReferenceImage={(path) =>
              void mc.attachExtraReferenceImage(path)
            }
            onRemoveExtraReferenceImage={mc.removeExtraReferenceImage}
            onClearReferenceImage={mc.clearReferenceImage}
            onOpenInpaintMask={() => mc.openInpaintMaskModal()}
            onOpenInpaintMaskModal={() => mc.openInpaintMaskModal()}
            inpaintCanvasFocus={mc.inpaintCanvasFocus}
            onInpaintCanvasFocusChange={mc.setInpaintCanvasFocus}
            onInpaintMaskChange={(path) => mc.setInpaintMaskPath(path)}
            onInpaintMaskSyncingChange={mc.setInpaintMaskSyncing}
            onOpenFullLog={() => setFullLogOpen(true)}
            activeModelLabel={mc.activeModelLabel}
            referenceModelFamily={mc.referenceModelFamily}
            onVaryImage={(amount) => void mc.runVaryImage(amount)}
            onAutoEnhance={(target) => void mc.runAutoEnhance(target)}
            resultCandidates={mc.resultCandidates}
            activeCandidatePath={mc.activeCandidatePath}
            onSelectResultCandidate={(path) => void mc.selectResultCandidate(path)}
            onRetryGeneration={() => void mc.runGenerate()}
            onUseCandidateAsSource={(path) => void mc.useCandidateAsSource(path)}
          />
          </div>
        </Panel>
        <PanelResizeHandle className="w-1 bg-dfui-border/50 transition hover:bg-dfui-accent/60" />
        <Panel defaultSize={24} minSize={20} maxSize={36} className="min-h-0">
          <div className="df-panel-shell">
          <InspectorPanel
            settings={mc.settings}
            onChange={mc.patchSettings}
            modelGallery={mc.modelGallery}
            loraGallery={mc.loraGallery}
            modelFilter={mc.modelFilter}
            onModelFilterChange={mc.setModelFilter}
            loraFilter={mc.loraFilter}
            onLoraFilterChange={mc.setLoraFilter}
            profileHints={mc.profileHints}
            galleryLoading={mc.galleryLoading}
            onSelectModel={(item) => void mc.selectModelGallery(item)}
            onToggleLora={mc.toggleLoraGallery}
            stylesList={mc.styleRecipes}
            aspectPresets={mc.aspectPresets}
            uiDefaults={mc.uiDefaults}
            activeModelLabel={mc.activeModelLabel}
            studioMode={mc.studioMode}
            onStyleChange={mc.setStyle}
            onRefreshInventory={mc.refreshStudioCatalog}
            modelDependencies={mc.modelDependencies}
            companionDownloadBusy={mc.companionDownloadBusy}
            onDownloadCompanions={() => void mc.downloadMissingCompanions()}
            onRefreshModelDependencies={() => void mc.refreshModelDependencies()}
            studioSettings={mc.studioSettings}
            onSaveStudioSettings={(patch) => void mc.saveStudioSettings(patch)}
            advancedMode={mc.advancedMode}
            simpleExperience={mc.uiExperience === "simple"}
            imageNumberMax={mc.imageNumberMax}
            civitaiApiKey={mc.appConfig?.ui.civitai_api_key ?? ""}
            generating={mc.generating}
            vramGb={mc.vramGb}
            mpsAvailable={mc.mpsAvailable}
            onAutomationStatus={mc.setStatusMessage}
            onRunAutomationBatch={mc.runAutomationBatch}
            onRefreshOutputs={() => void mc.refreshOutputs({ selectNewest: true })}
            onBeforeAutomationRun={mc.ensureCreativeAssetsReady}
            onRevealPath={(path) => void mc.openOutputInExplorer(path)}
          />
          </div>
        </Panel>
      </PanelGroup>
      <FullLogModal
        open={fullLogOpen}
        jobId={mc.logJobId}
        onClose={() => setFullLogOpen(false)}
      />
      <InpaintMaskModal
        open={mc.inpaintMaskOpen}
        imagePath={mc.settings.input_image ?? ""}
        initialMaskPath={mc.settings.inpaint_mask_path}
        onClose={() => mc.setInpaintMaskOpen(false)}
        onMaskChange={(path) => mc.setInpaintMaskPath(path)}
        onMaskSyncingChange={mc.setInpaintMaskSyncing}
        onSave={(path) => {
          mc.setInpaintMaskPath(path);
          mc.setInpaintMaskOpen(false);
        }}
      />
      <AppSettingsModal
        open={appSettingsOpen}
        onClose={() => setAppSettingsOpen(false)}
        appConfig={mc.appConfig}
        onSaveAppConfig={(patch) => void mc.saveAppConfig(patch)}
        agentProviders={mc.agentProviders}
        agentProviderTest={mc.agentProviderTest}
        agentProviderBusy={mc.agentProviderBusy}
        onTestAgentProvider={(patch) => void mc.testAgentProvider(patch)}
        studioSettings={mc.studioSettings}
        onSaveStudioSettings={(patch) => void mc.saveStudioSettings(patch)}
        userStyleProfile={mc.userStyleProfile}
        userStyleProfilePath={mc.userStyleProfilePath}
        onUserStyleMemoryEnabledChange={(enabled) =>
          void mc.setUserStyleMemoryEnabled(enabled)
        }
        onClearUserStyleMemory={() => void mc.clearUserStyleMemory()}
        onExportUserStyleMemory={() => void mc.exportUserStyleMemory()}
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
        onCopyLinks={mc.companionDownload.copyLinks}
        onCopyManualList={mc.companionDownload.copyManualList}
        onRetry={mc.companionDownload.retry}
      />
      </div>
    </>
  );
}
