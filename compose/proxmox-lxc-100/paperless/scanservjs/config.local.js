// Read by scanservjs at start-up (restart the container after a change).
module.exports = {
  afterConfig(config) {
    // Upstream offers only the standard collate order; the reverse one exists
    // in the code but not in the list. It is the fallback if the flipped
    // stack comes back in the other order on this feeder.
    config.batchModes.push('auto-collate-reverse');
    // PDF only. An image format with more than one page comes out as a zip,
    // and Paperless cannot consume a zip: the first real scan (2026-09-26)
    // sat in the consume folder as scan_*.zip because the UI default was JPG.
    // The OCR variant is dropped as well, Paperless runs its own OCR.
    const pdf = config.pipelines.filter(p => p.description.startsWith('PDF (JPG'));
    // Medium quality first: the first pipeline is the default.
    config.pipelines = [
      ...pdf.filter(p => p.description.includes('medium')),
      ...pdf.filter(p => !p.description.includes('medium'))
    ];
  },

  afterDevices(devices) {
    devices.forEach(device => {
      const f = device.features;
      if (f['--source']) f['--source'].default = 'ADF';
      if (f['--resolution']) f['--resolution'].default = 300;
      if (f['--mode']) f['--mode'].default = 'Gray';
      // Single-sided feeder run. Double-sided paper still needs the collate
      // mode picked by hand: as a default it would ask for a second pass on
      // every one-sided letter.
      device.settings.batchMode.default = 'auto';
    });
  }
};
