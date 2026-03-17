import { astro } from 'iztro';

function hourToTimeIndex(hour) {
  if (hour === 23) return 12;
  if (hour === 0) return 0;
  return Math.floor((hour + 1) / 2);
}

function starList(stars) {
  return (stars || []).map((star) => ({
    name: star.name,
    brightness: star.brightness,
    type: star.type,
    scope: star.scope,
    mutagen: star.mutagen,
  }));
}

function serializePalace(palace) {
  const flyPlaces = typeof palace.mutagedPlaces === 'function' ? palace.mutagedPlaces() : [];
  const flyMutagen = ['化禄', '化权', '化科', '化忌'].map((type, idx) => ({
    type,
    to: flyPlaces[idx]?.name || null,
  }));

  return {
    name: palace.name,
    heavenlyStem: palace.heavenlyStem,
    earthlyBranch: palace.earthlyBranch,
    bodyPalace: palace.isBodyPalace,
    originPalace: palace.isOriginalPalace,
    majorStars: starList(palace.majorStars),
    minorStars: starList(palace.minorStars),
    adjectiveStars: starList(palace.adjectiveStars),
    changsheng12: palace.changsheng12,
    boshi12: palace.boshi12,
    jiangqian12: palace.jiangqian12,
    suiqian12: palace.suiqian12,
    decadal: palace.decadal,
    flyMutagen,
  };
}

function main() {
  const payloadRaw = process.argv[2];
  if (!payloadRaw) {
    console.error('missing payload');
    process.exit(2);
  }
  const payload = JSON.parse(payloadRaw);
  const timeIndex = hourToTimeIndex(Number(payload.hour));
  const gender = payload.gender === '女' ? 'female' : 'male';

  const chart = astro.byLunar(payload.lunar_date, timeIndex, gender, Boolean(payload.is_leap_month), 'zh-CN');
  // Required for palace-level fly-transform helpers.
  chart.palaces.forEach((p) => p.setAstrolabe(chart));
  const h = chart.horoscope();
  const year = h.yearly || {};

  const palaceRows = chart.palaces.map(serializePalace);
  const transform = {
    yearMutagen: (year.mutagen || []).map((name, idx) => ({
      type: ['化禄', '化权', '化科', '化忌'][idx] || `化${idx}`,
      star: name,
      to: year.palaceNames ? year.palaceNames[idx] : undefined,
    })),
    flyingStars: year.yearlyDecStar || {},
  };

  const output = {
    gender: chart.gender,
    solarDate: chart.solarDate,
    lunarDate: chart.lunarDate,
    chineseDate: chart.chineseDate,
    time: chart.time,
    timeRange: chart.timeRange,
    sign: chart.sign,
    zodiac: chart.zodiac,
    soul: chart.soul,
    body: chart.body,
    fiveElementsClass: chart.fiveElementsClass,
    rawDates: chart.rawDates,
    palaces: palaceRows,
    transforms: transform,
  };

  process.stdout.write(JSON.stringify(output));
}

main();
