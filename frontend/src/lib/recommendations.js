export function appendMoreRecommendedCards(current, newCards) {
  const currentCards = current?.suggested_cards || [];
  const existingMore = current?.recommended_sections
    ?.find((section) => section.id === 'more_finds')
    ?.cards || [];
  const baseSections = (current?.recommended_sections || [])
    .filter((section) => section.id !== 'more_finds')
    .map((section) => ({ ...section, cards: section.cards || [] }));

  return {
    ...current,
    suggested_cards: [...currentCards, ...newCards],
    recommended_sections: [
      ...baseSections,
      {
        id: 'more_finds',
        label: 'More Finds',
        cards: [...existingMore, ...newCards],
      },
    ],
  };
}
